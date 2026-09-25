#include "extract_nav.h"

#include <algorithm>
#include <map>
#include <set>

#include "common/util/Assert.h"

#include "fmt/format.h"
#include "third-party/json.hpp"

namespace level_tools {

namespace {
// A GOAL object (or the part of an array a label points into): from a label, or from the type tag
// just before it for a basic, to the next one.
struct Chunk {
  int start = 0;
  int end = 0;
};
}  // namespace

DataGraphCopy copy_data_graph(const decompiler::LinkedObjectFile& file,
                              int seg,
                              const std::vector<std::pair<std::string, int>>& roots) {
  const auto& words = file.words_by_seg.at(seg);
  const int seg_bytes = (int)words.size() * 4;

  // chunk boundaries
  std::set<int> starts;
  for (const auto& label : file.labels) {
    if (label.target_segment != seg) {
      continue;
    }
    int start = label.offset & ~3;
    if (start >= 4 && words.at(start / 4 - 1).kind() == decompiler::LinkedWord::TYPE_PTR) {
      start -= 4;
    }
    starts.insert(start);
  }
  std::vector<Chunk> chunks;
  for (auto it = starts.begin(); it != starts.end(); ++it) {
    auto next = std::next(it);
    chunks.push_back({*it, next == starts.end() ? seg_bytes : *next});
  }
  auto chunk_of = [&](int byte) {
    auto it = std::upper_bound(chunks.begin(), chunks.end(), byte,
                               [](int b, const Chunk& c) { return b < c.start; });
    ASSERT_MSG(it != chunks.begin(), fmt::format("no chunk holds byte {}", byte));
    return (int)(it - chunks.begin()) - 1;
  };
  auto label_target = [&](const decompiler::LinkedWord& word) {
    const auto& label = file.labels.at(word.label_id());
    ASSERT_MSG(label.target_segment == seg, "data graph pointer to another segment");
    return label.offset;
  };
  // A res-lump's data-top (entities are res-lumps) points just past its data, so to the next
  // object: it isn't followed, and is rebuilt from data-base and data-size.
  auto is_data_top = [&](const Chunk& chunk, int byte) {
    if (byte != chunk.start + 16) {
      return false;
    }
    const auto& tag = words.at(chunk.start / 4);
    if (tag.kind() != decompiler::LinkedWord::TYPE_PTR) {
      return false;
    }
    const auto type = tag.symbol_name();
    return type == "res-lump" || type.rfind("entity", 0) == 0;
  };

  // the chunks the roots lead to
  std::vector<int> root_targets;
  std::set<int> visited;
  std::vector<int> todo;
  for (const auto& [name, byte] : roots) {
    const auto& word = words.at(byte / 4);
    if (word.kind() != decompiler::LinkedWord::PTR) {
      root_targets.push_back(-1);
      continue;
    }
    int target = label_target(word);
    root_targets.push_back(target);
    int c = chunk_of(target);
    if (visited.insert(c).second) {
      todo.push_back(c);
    }
  }
  while (!todo.empty()) {
    int c = todo.back();
    todo.pop_back();
    for (int b = chunks[c].start; b < chunks[c].end; b += 4) {
      const auto& word = words.at(b / 4);
      if (word.kind() == decompiler::LinkedWord::PTR && !is_data_top(chunks[c], b)) {
        int next = chunk_of(label_target(word));
        if (visited.insert(next).second) {
          todo.push_back(next);
        }
      }
    }
  }

  // copy them in their order, each at its original offset modulo 16
  DataGraphCopy out;
  std::map<int, int> delta;  // chunk -> copy byte - original byte
  for (int c : visited) {
    int cur = (int)out.words.size() * 4;
    int pad = ((chunks[c].start - cur) % 16 + 16) % 16;
    for (int i = 0; i < pad / 4; i++) {
      out.words.push_back(0);
    }
    delta[c] = (int)out.words.size() * 4 - chunks[c].start;
    out.words.resize(out.words.size() + (chunks[c].end - chunks[c].start) / 4, 0);
  }
  for (int c : visited) {
    for (int b = chunks[c].start; b < chunks[c].end; b += 4) {
      const auto& word = words.at(b / 4);
      int idx = (b + delta[c]) / 4;
      switch (word.kind()) {
        case decompiler::LinkedWord::PLAIN_DATA:
          out.words.at(idx) = word.data;
          break;
        case decompiler::LinkedWord::PTR: {
          if (is_data_top(chunks[c], b)) {
            const auto& base = words.at(b / 4 - 1);
            const auto& size = words.at(b / 4 + 1);
            if (base.kind() == decompiler::LinkedWord::PTR &&
                size.kind() == decompiler::LinkedWord::PLAIN_DATA) {
              int base_target = label_target(base);
              out.pointers.emplace_back(
                  idx, base_target + delta.at(chunk_of(base_target)) + (int)size.data);
            }
            break;
          }
          int target = label_target(word);
          out.pointers.emplace_back(idx, target + delta.at(chunk_of(target)));
        } break;
        case decompiler::LinkedWord::TYPE_PTR:
          out.types.emplace_back(idx, word.symbol_name());
          break;
        case decompiler::LinkedWord::SYM_PTR:
          out.symbols.emplace_back(idx, word.symbol_name());
          break;
        case decompiler::LinkedWord::EMPTY_PTR:
          out.empty_lists.push_back(idx);
          break;
        default:
          ASSERT_MSG(false, fmt::format("data graph: unsupported word kind {} at byte {}",
                                        (int)word.kind(), b));
      }
    }
  }
  for (size_t i = 0; i < roots.size(); i++) {
    if (root_targets[i] >= 0) {
      out.roots.emplace_back(roots[i].first,
                             root_targets[i] + delta.at(chunk_of(root_targets[i])));
    }
  }
  return out;
}

std::string data_graph_copy_to_json(const DataGraphCopy& copy) {
  nlohmann::json j;
  j["words"] = copy.words;
  j["pointers"] = copy.pointers;
  j["types"] = copy.types;
  j["symbols"] = copy.symbols;
  j["empty_lists"] = copy.empty_lists;
  auto& roots = j["roots"];
  roots = nlohmann::json::object();
  for (const auto& [name, byte] : copy.roots) {
    roots[name] = byte;
  }
  return j.dump();
}

}  // namespace level_tools
