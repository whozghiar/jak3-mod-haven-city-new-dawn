#include "DataBlob.h"

#include "common/util/FileUtil.h"
#include "common/util/json_util.h"

DataBlob DataBlob::from_json_file(const std::string& path) {
  auto j = parse_commented_json(file_util::read_text_file(file_util::get_file_path({path})), path);
  DataBlob blob;
  blob.words = j.at("words").get<std::vector<u32>>();
  blob.pointers = j.at("pointers").get<std::vector<std::pair<int, int>>>();
  blob.types = j.at("types").get<std::vector<std::pair<int, std::string>>>();
  blob.symbols = j.at("symbols").get<std::vector<std::pair<int, std::string>>>();
  blob.empty_lists = j.at("empty_lists").get<std::vector<int>>();
  blob.roots = j.at("roots").get<std::map<std::string, int>>();
  return blob;
}

int DataBlob::add_to(DataObjectGenerator& gen) const {
  gen.align(4);
  const int base_word = gen.words();
  for (auto w : words) {
    gen.add_word(w);
  }
  for (const auto& [word, byte] : pointers) {
    gen.link_word_to_byte(base_word + word, base_word * 4 + byte);
  }
  for (const auto& [word, name] : types) {
    gen.link_word_to_type(name, base_word + word);
  }
  for (const auto& [word, name] : symbols) {
    gen.link_word_to_symbol(name, base_word + word);
  }
  for (int word : empty_lists) {
    gen.link_word_to_symbol("_empty_", base_word + word);
  }
  return base_word * 4;
}
