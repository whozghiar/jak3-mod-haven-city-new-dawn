#include "Tools.h"

#include <cctype>
#include <cstring>
#include <map>
#include <set>

#include "common/goos/ParseHelpers.h"
#include "common/util/DgoWriter.h"
#include "common/util/FileUtil.h"

#include "goalc/build_actor/jak1/build_actor.h"
#include "goalc/build_level/jak1/build_level.h"
#include "goalc/build_level/jak2/build_level.h"
#include "goalc/build_level/jak3/build_level.h"
#include "goalc/build_sbk/build_sbk.h"
#include "goalc/compiler/Compiler.h"
#include "goalc/data_compiler/dir_tpages.h"
#include "goalc/data_compiler/game_count.h"
#include "goalc/data_compiler/game_text_common.h"

#include "fmt/format.h"

CompilerTool::CompilerTool(Compiler* compiler) : Tool("goalc"), m_compiler(compiler) {}

bool CompilerTool::needs_run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() != 1) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }

  if (!m_compiler->knows_object_file(fs::path(task.input.at(0)).stem().string())) {
    return true;
  }
  return Tool::needs_run(task, path_map);
}

bool CompilerTool::run(const ToolInput& task, const PathMap& /*path_map*/) {
  // todo check inputs
  try {
    CompilationOptions options;
    options.filename = task.input.at(0);
    options.color = true;
    options.write = true;
    m_compiler->asm_file(options);
  } catch (std::exception& e) {
    lg::print("Compilation failed: {}\n", e.what());
    return false;
  }
  return true;
}

namespace {
DgoDescription parse_desc_file(const std::string& filename, goos::Reader& reader) {
  auto& dgo_desc = reader.read_from_file({filename}).as_pair()->cdr;
  if (goos::list_length(dgo_desc) != 1) {
    throw std::runtime_error("Invalid DGO description - got too many lists");
  }
  auto& dgo = dgo_desc.as_pair()->car;

  DgoDescription desc;
  auto& first = dgo.as_pair()->car;
  desc.dgo_name = first.as_string()->data;
  auto& dgo_rest = dgo.as_pair()->cdr.as_pair()->car;

  for_each_in_list(dgo_rest, [&](const goos::Object& entry) {
    if (!entry.is_string()) {
      throw std::runtime_error(fmt::format("Invalid file name for DGO: {}\n", entry.print()));
    }

    DgoDescription::DgoEntry o;
    const auto& file_name = entry.as_string()->data;
    // automatically deduce dgo name
    // (not really a fan of how this is written...)
    if (file_name.length() > 2 && file_name.substr(file_name.length() - 2, 2) == ".o") {
      // ends with .o so it's a code file
      o.name_in_dgo = file_name.substr(0, file_name.length() - 2);
    } else if (file_name.length() > 6 && file_name.substr(file_name.length() - 6, 6) == "-ag.go") {
      // ends with -ag.go so it's an art group file
      o.name_in_dgo = file_name.substr(0, file_name.length() - 6);
    } else if (file_name.length() > 3 && file_name.substr(file_name.length() - 3, 3) == ".go") {
      // ends with .go so it's a generic data file
      o.name_in_dgo = file_name.substr(0, file_name.length() - 3);
    }
    o.file_name = file_name;
    desc.entries.push_back(o);
  });
  return desc;
}
}  // namespace

DgoTool::DgoTool() : Tool("dgo") {}

bool DgoTool::run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() != 1) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  auto desc = parse_desc_file(task.input.at(0), m_reader);
  build_dgo(desc, path_map.output_prefix);
  return true;
}

std::vector<std::string> DgoTool::get_additional_dependencies(const ToolInput& task,
                                                              const PathMap& path_map) {
  std::vector<std::string> result;
  auto desc = parse_desc_file(task.input.at(0), m_reader);
  for (auto& x : desc.entries) {
    // todo out
    result.push_back(fmt::format("out/{}obj/{}", path_map.output_prefix, x.file_name));
  }
  return result;
}

TpageDirTool::TpageDirTool() : Tool("tpage-dir") {}

bool TpageDirTool::run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() != 1) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  compile_dir_tpages(task.input.at(0), path_map.output_prefix);
  return true;
}

CopyTool::CopyTool() : Tool("copy") {}

bool CopyTool::run(const ToolInput& task, const PathMap& /*path_map*/) {
  if (task.input.size() != 1) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  for (auto& out : task.output) {
    fs::copy(fs::path(file_util::get_file_path({task.input.at(0)})),
             fs::path(file_util::get_file_path({out})), fs::copy_options::overwrite_existing);
  }
  return true;
}

GameCntTool::GameCntTool() : Tool("game-cnt") {}

bool GameCntTool::run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() != 1) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  compile_game_count(task.input.at(0), path_map.output_prefix);
  return true;
}

TextTool::TextTool() : Tool("text") {}

bool TextTool::needs_run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() != 1) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }

  std::vector<std::string> deps;
  std::vector<GameTextDefinitionFile> files;
  open_text_project("text", task.input.at(0), files);
  for (auto& file : files) {
    deps.push_back(path_map.apply_remaps(file.file_path));
  }
  return Tool::needs_run({task.input, deps, task.output, task.arg}, path_map);
}

bool TextTool::run(const ToolInput& task, const PathMap& path_map) {
  GameTextDB db;
  std::vector<GameTextDefinitionFile> files;
  open_text_project("text", task.input.at(0), files);
  for (auto& file : files) {
    file.file_path = path_map.apply_remaps(file.file_path);
  }
  compile_game_text(files, db, path_map.output_prefix);
  return true;
}

GroupTool::GroupTool() : Tool("group") {}

bool GroupTool::run(const ToolInput&, const PathMap& /*path_map*/) {
  return true;
}

void enumerate_subtitle_project_files(const std::string& tool_name,
                                      const std::string& file_path,
                                      const PathMap& path_map,
                                      std::vector<GameSubtitleDefinitionFile>& files,
                                      std::vector<std::string>& deps) {
  open_subtitle_project(tool_name, file_path, files);
  for (auto& file : files) {
    deps.push_back(path_map.apply_remaps(file.lines_path));
    deps.push_back(path_map.apply_remaps(file.meta_path));
    if (file.lines_base_path) {
      deps.push_back(path_map.apply_remaps(file.lines_base_path.value()));
    }
    if (file.meta_base_path) {
      deps.push_back(path_map.apply_remaps(file.meta_base_path.value()));
    }
  }
}

void run_subtitle_project_files(const std::string& tool_name,
                                const std::string& file_path,
                                const PathMap& path_map,
                                std::vector<GameSubtitleDefinitionFile>& files) {
  open_subtitle_project(tool_name, file_path, files);
  for (auto& file : files) {
    file.lines_path = path_map.apply_remaps(file.lines_path);
    file.meta_path = path_map.apply_remaps(file.meta_path);
    if (file.lines_base_path) {
      file.lines_base_path = path_map.apply_remaps(file.lines_base_path.value());
    }
    if (file.meta_base_path) {
      file.meta_base_path = path_map.apply_remaps(file.meta_base_path.value());
    }
  }
}

SubtitleTool::SubtitleTool() : Tool("subtitle") {}

bool SubtitleTool::needs_run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() != 1) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  std::vector<GameSubtitleDefinitionFile> files;
  std::vector<std::string> deps;
  enumerate_subtitle_project_files(name(), task.input.at(0), path_map, files, deps);
  return Tool::needs_run({task.input, deps, task.output, task.arg}, path_map);
}

bool SubtitleTool::run(const ToolInput& task, const PathMap& path_map) {
  GameSubtitleDB db;
  db.m_subtitle_version = GameSubtitleDB::SubtitleFormat::V1;
  std::vector<GameSubtitleDefinitionFile> files;
  run_subtitle_project_files(name(), task.input.at(0), path_map, files);
  compile_game_subtitles(files, db, path_map.output_prefix);
  return true;
}

SubtitleV2Tool::SubtitleV2Tool() : Tool("subtitle-v2") {}

bool SubtitleV2Tool::needs_run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() != 1) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  std::vector<GameSubtitleDefinitionFile> files;
  std::vector<std::string> deps;
  enumerate_subtitle_project_files(name(), task.input.at(0), path_map, files, deps);
  return Tool::needs_run({task.input, deps, task.output, task.arg}, path_map);
}

bool SubtitleV2Tool::run(const ToolInput& task, const PathMap& path_map) {
  GameSubtitleDB db;
  db.m_subtitle_version = GameSubtitleDB::SubtitleFormat::V2;
  std::vector<GameSubtitleDefinitionFile> files;
  run_subtitle_project_files(name(), task.input.at(0), path_map, files);
  compile_game_subtitles(files, db, path_map.output_prefix);
  return true;
}

BuildLevelTool::BuildLevelTool() : Tool("build-level") {}

bool BuildLevelTool::needs_run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() > 3) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  auto deps = get_build_level_deps(task.input.at(0));
  auto rerun = task.input.at(1) == "#t";
  std::vector in = {task.input.at(0)};
  return rerun || Tool::needs_run({in, deps, task.output, task.arg}, path_map);
}

bool BuildLevelTool::run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() > 3) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  auto gen_fr3 = task.input.at(2) == "#t";
  return jak1::run_build_level(task.input.at(0), task.output.at(0), path_map.output_prefix,
                               gen_fr3);
}

BuildLevel2Tool::BuildLevel2Tool() : Tool("build-level2") {}

bool BuildLevel2Tool::needs_run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() > 3) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  auto deps = get_build_level_deps(task.input.at(0));
  auto rerun = task.input.at(1) == "#t";
  std::vector in = {task.input.at(0)};
  return rerun || Tool::needs_run({in, deps, task.output, task.arg}, path_map);
}

bool BuildLevel2Tool::run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() > 3) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  auto gen_fr3 = task.input.at(2) == "#t";
  return jak2::run_build_level(task.input.at(0), task.output.at(0), path_map.output_prefix,
                               gen_fr3);
}

BuildLevel3Tool::BuildLevel3Tool() : Tool("build-level3") {}

bool BuildLevel3Tool::needs_run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() > 3) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  auto deps = get_build_level_deps(task.input.at(0));
  auto rerun = task.input.at(1) == "#t";
  std::vector in = {task.input.at(0)};
  return rerun || Tool::needs_run({in, deps, task.output, task.arg}, path_map);
}

bool BuildLevel3Tool::run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() > 3) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  auto gen_fr3 = task.input.at(2) == "#t";
  return jak3::run_build_level(task.input.at(0), task.output.at(0), path_map.output_prefix,
                               gen_fr3);
}

BuildActorTool::BuildActorTool() : Tool("build-actor") {}

bool BuildActorTool::needs_run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() > 8) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  auto rerun = task.input.at(2) == "#t";
  std::vector deps{task.input.at(0)};
  return rerun || Tool::needs_run({deps, deps, task.output, task.arg}, path_map);
}

bool BuildActorTool::run(const ToolInput& task, const PathMap& path_map) {
  (void)path_map;
  if (task.input.size() > 8) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  jak1::BuildActorParams1 params;
  params.gen_collide_mesh = task.input.at(1) == "#t";
  if (task.input.at(3) == "#f") {
    params.texture_bucket = -1;
  } else {
    try {
      params.texture_bucket = static_cast<s8>(std::stoi(task.input.at(3)));
    } catch (std::invalid_argument&) {
      throw std::runtime_error("[build-actor] texture-bucket must be #f or a valid integer.");
    }
  }
  params.framerate = std::stof(task.input.at(4));
  if (task.input.at(5) != "#f") {
    params.master_art_group = task.input.at(5);
  }
  auto master_ag_list = m_reader.read_from_string(task.input.at(6));
  // e.g. ((jakb-board-stance 180) (jakb-board-airwalk 181))
  if (!master_ag_list.as_pair()->cdr.is_empty_list()) {
    std::map<std::string, int> master_ag_map;
    goos::for_each_in_list(master_ag_list.as_pair()->cdr.as_pair()->car,
                           [&](const goos::Object& o) {
                             auto map = o.as_pair();
                             auto ja = std::string(map->car.as_symbol().name_ptr);
                             auto idx = map->cdr.as_pair()->car.as_int();
                             master_ag_map.insert({ja, idx});
                           });
    params.master_ag_map = master_ag_map;
  }
  if (task.input.at(7) != "6") {
    params.joint_channel = std::stoi(task.input.at(7));
  }
  return jak1::run_build_actor(task.input.at(0), task.output.at(0), params);
}

BuildActor2Tool::BuildActor2Tool() : Tool("build-actor2") {}

bool BuildActor2Tool::needs_run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() > 8) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  auto rerun = task.input.at(2) == "#t";
  std::vector deps{task.input.at(0)};
  return rerun || Tool::needs_run({deps, deps, task.output, task.arg}, path_map);
}

bool BuildActor2Tool::run(const ToolInput& task, const PathMap& path_map) {
  (void)path_map;
  if (task.input.size() > 8) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  jak2::BuildActorParams2 params;
  params.gen_collide_mesh = task.input.at(1) == "#t";
  if (task.input.at(3) == "#f") {
    params.texture_bucket = -1;
  } else {
    try {
      params.texture_bucket = static_cast<s8>(std::stoi(task.input.at(3)));
    } catch (std::invalid_argument&) {
      throw std::runtime_error("[build-actor2] texture-bucket must be #f or a valid integer.");
    }
  }
  params.framerate = std::stof(task.input.at(4));
  if (task.input.at(5) != "#f") {
    params.master_art_group = task.input.at(5);
  }
  auto master_ag_list = m_reader.read_from_string(task.input.at(6));
  if (!master_ag_list.as_pair()->cdr.is_empty_list()) {
    std::map<std::string, int> master_ag_map;
    goos::for_each_in_list(master_ag_list.as_pair()->cdr.as_pair()->car,
                           [&](const goos::Object& o) {
                             auto map = o.as_pair();
                             auto ja = std::string(map->car.as_symbol().name_ptr);
                             auto idx = map->cdr.as_pair()->car.as_int();
                             master_ag_map.insert({ja, idx});
                           });
    params.master_ag_map = master_ag_map;
  }
  if (task.input.at(7) != "6") {
    params.joint_channel = std::stoi(task.input.at(7));
  }
  return jak2::run_build_actor(task.input.at(0), task.output.at(0), params);
}

BuildActor3Tool::BuildActor3Tool() : Tool("build-actor3") {}

bool BuildActor3Tool::needs_run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() > 8) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  auto rerun = task.input.at(2) == "#t";
  std::vector deps{task.input.at(0)};
  return rerun || Tool::needs_run({deps, deps, task.output, task.arg}, path_map);
}

bool BuildActor3Tool::run(const ToolInput& task, const PathMap& path_map) {
  (void)path_map;
  if (task.input.size() > 8) {
    throw std::runtime_error(fmt::format("Invalid amount of inputs to {} tool", name()));
  }
  jak3::BuildActorParams3 params;
  params.gen_collide_mesh = task.input.at(1) == "#t";
  if (task.input.at(3) == "#f") {
    params.texture_bucket = -1;
  } else {
    try {
      params.texture_bucket = static_cast<s8>(std::stoi(task.input.at(3)));
    } catch (std::invalid_argument&) {
      throw std::runtime_error("[build-actor3] texture-bucket must be #f or a valid integer.");
    }
  }
  params.framerate = std::stof(task.input.at(4));
  if (task.input.at(5) != "#f") {
    params.master_art_group = task.input.at(5);
  }
  auto master_ag_list = m_reader.read_from_string(task.input.at(6));
  if (!master_ag_list.as_pair()->cdr.is_empty_list()) {
    std::map<std::string, int> master_ag_map;
    goos::for_each_in_list(master_ag_list.as_pair()->cdr.as_pair()->car,
                           [&](const goos::Object& o) {
                             auto map = o.as_pair();
                             auto ja = std::string(map->car.as_symbol().name_ptr);
                             auto idx = map->cdr.as_pair()->car.as_int();
                             master_ag_map.insert({ja, idx});
                           });
    params.master_ag_map = master_ag_map;
  }
  if (task.input.at(7) != "6") {
    params.joint_channel = std::stoi(task.input.at(7));
  }
  return jak3::run_build_actor(task.input.at(0), task.output.at(0), params);
}

namespace {
// Parses a quoted GOOS list of symbol names, e.g. '(board-charge board-launch), from its
// printed-string form. Used by build-sbk/append-sbk to read the (optional) list of sound
// names that should be pulled out of metadata.txt - the same pattern BuildActorTool uses to
// parse :master-ag-map. An empty result means "no filter" (use every sound in metadata.txt).
std::vector<std::string> parse_name_list(goos::Reader& reader, const std::string& text) {
  std::vector<std::string> names;
  auto list = reader.read_from_string(text);
  if (!list.as_pair()->cdr.is_empty_list()) {
    goos::for_each_in_list(list.as_pair()->cdr.as_pair()->car, [&](const goos::Object& o) {
      names.push_back(std::string(o.as_symbol().name_ptr));
    });
  }
  return names;
}
}  // namespace

BuildSbkTool::BuildSbkTool() : Tool("build-sbk") {}

bool BuildSbkTool::needs_run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.empty()) {
    throw std::runtime_error("[build-sbk] Expected at least 1 input (source dir)");
  }
  bool force = task.input.size() > 1 && task.input.at(1) == "#t";
  std::vector<std::string> deps{task.input.at(0)};
  return force || Tool::needs_run({deps, deps, task.output, task.arg}, path_map);
}

bool BuildSbkTool::run(const ToolInput& task, const PathMap&) {
  if (task.input.empty()) {
    throw std::runtime_error("[build-sbk] Expected at least 1 input (source dir)");
  }

  sbk::BuildOptions opts;
  if (task.input.size() > 2) {
    opts.bank_id = std::stoi(task.input.at(2));
  }
  if (task.input.size() > 3) {
    opts.jak1_format = task.input.at(3) == "#t";
  }
  std::vector<std::string> only_names;
  if (task.input.size() > 4) {
    only_names = parse_name_list(m_reader, task.input.at(4));
  }

  sbk::create_sbk_from_dir(file_util::get_file_path({task.input.at(0)}),
                           file_util::get_file_path({task.output.at(0)}), opts, only_names);
  return true;
}

namespace {
// A VAG file name packed like the Jak 3 overlord's PackVAGFileName (game/overlord/jak3/
// isocommon.cpp): 8 characters (A-Z, 0-9, '-', space), each half of 4 in base 38, the first half
// above the second: 42 bits.
u64 pack_vag_name(const std::string& name) {
  if (name.size() > 8) {
    throw std::runtime_error(fmt::format("[pack-vags] {} is longer than 8 characters", name));
  }
  u64 halves[2] = {0, 0};
  for (int i = 0; i < 8; i++) {
    char c = i < (int)name.size() ? (char)toupper(name[i]) : ' ';
    u64 v;
    if (c >= 'A' && c <= 'Z') {
      v = c - 'A' + 1;
    } else if (c >= '0' && c <= '9') {
      v = c - '0' + 27;
    } else if (c == '-') {
      v = 37;
    } else if (c == ' ') {
      v = 0;
    } else {
      throw std::runtime_error(fmt::format("[pack-vags] invalid character in {}", name));
    }
    halves[i / 4] = halves[i / 4] * 38 + v;
  }
  return (halves[0] << 21) | halves[1];
}

// a field of a VAG header: big endian after "VAGp", little endian after "pGAV" (both are found)
u32 vag_header_field(const u8* header, int offset) {
  const u8* p = header + offset;
  if (memcmp(header, "VAGp", 4) == 0) {
    return ((u32)p[0] << 24) | ((u32)p[1] << 16) | ((u32)p[2] << 8) | p[3];
  }
  return ((u32)p[3] << 24) | ((u32)p[2] << 16) | ((u32)p[1] << 8) | p[0];
}

// size bytes of a file from offset (the wads are big: only the lines are read)
std::vector<u8> read_file_range(const fs::path& path, size_t offset, size_t size) {
  std::vector<u8> out(size);
  FILE* fp = file_util::open_file(path, "rb");
  if (!fp || fseek(fp, (long)offset, SEEK_SET) != 0 || fread(out.data(), 1, size, fp) != size) {
    if (fp) {
      fclose(fp);
    }
    throw std::runtime_error(fmt::format("[pack-vags] failed to read {}", path.string()));
  }
  fclose(fp);
  return out;
}

std::string upper_trimmed(std::string s) {
  while (!s.empty() && (s.back() == ' ' || s.back() == 0)) {
    s.pop_back();
  }
  for (auto& c : s) {
    c = (char)toupper(c);
  }
  return s;
}
}  // namespace

PackVagsTool::PackVagsTool() : Tool("pack-vags") {}

/*!
 * in: (Jak 2's VAGDIR.AYB, the Jak 3 VAGDIR.AYB the game uses, optionally the file listing the
 * lines, only so that its change packs again), the wads next to the first (VAGWAD.<language>).
 * arg: the lines, each a name or (name new-name). out: the directory, then a wad per language
 * (from Jak 2's English one when Jak 2's disc lacks the language).
 * Jak 2's directory: a count, then {8 characters, start in 2048 byte sectors, stereo}. Jak 3's: a
 * header, then a 64-bit entry per line: name (42 bits), stereo, international, sample rate index,
 * start in 32 KB pages (the same in every language's wad: a line takes the pages of its longest
 * language). A line is its VAG header and its ADPCM data, the same in both games. A new name must
 * not be one of the Jak 3 directory's.
 */
bool PackVagsTool::run(const ToolInput& task, const PathMap&) {
  if (task.input.size() < 2 || task.input.size() > 3 || task.output.size() < 2) {
    throw std::runtime_error("[pack-vags] Expected 2 or 3 inputs and at least 2 outputs");
  }
  auto src_dir_path = file_util::get_file_path({task.input.at(0)});
  auto src_dir = file_util::read_binary_file(src_dir_path);
  auto target_dir = file_util::read_binary_file(file_util::get_file_path({task.input.at(1)}));

  // Jak 2's lines by name: their start (bytes) and stereo flag
  std::map<std::string, std::pair<size_t, u32>> src_lines;
  u32 count;
  memcpy(&count, src_dir.data(), 4);
  for (u32 i = 0; i < count; i++) {
    const u8* e = src_dir.data() + 4 + i * 16;
    u32 sector, stereo;
    memcpy(&sector, e + 8, 4);
    memcpy(&stereo, e + 12, 4);
    src_lines[upper_trimmed(std::string((const char*)e, 8))] = {(size_t)sector * 2048, stereo};
  }

  // the Jak 3 directory's names
  std::set<u64> taken;
  u32 target_count;
  memcpy(&target_count, target_dir.data() + 12, 4);
  for (u32 i = 0; i < target_count; i++) {
    u64 e;
    memcpy(&e, target_dir.data() + 16 + i * 8, 8);
    taken.insert(e & ((1ull << 42) - 1));
  }

  // the lines: (Jak 2 name, new name)
  std::vector<std::pair<std::string, std::string>> lines;
  goos::for_each_in_list(task.arg, [&](const goos::Object& o) {
    if (o.is_pair()) {
      lines.push_back({upper_trimmed(o.as_pair()->car.print()),
                       upper_trimmed(o.as_pair()->cdr.as_pair()->car.print())});
    } else {
      lines.push_back({upper_trimmed(o.print()), upper_trimmed(o.print())});
    }
  });

  // each language's wad: Jak 2's, its English one if missing
  auto src_folder = fs::path(src_dir_path).parent_path();
  std::vector<fs::path> src_wads;
  for (size_t i = 1; i < task.output.size(); i++) {
    auto lang = fs::path(task.output.at(i)).extension().string();
    auto wad = src_folder / ("VAGWAD" + lang);
    if (!fs::exists(wad)) {
      wad = src_folder / "VAGWAD.ENG";
    }
    src_wads.push_back(wad);
  }

  // sample rates by index (the Jak 3 overlord's table, game/overlord/jak3/iso.cpp)
  constexpr u32 kRates[16] = {0xFA00, 0x1F40, 0x3E80, 0x5DC0, 0x7D00, 0x9C40, 0xBB80, 0xDAC0,
                              0xAC44, 0x1589, 0x2B11, 0x409A, 0x5622, 0x6BAB, 0x8133, 0x96BC};
  constexpr size_t kPage = 0x8000;
  std::vector<u64> entries;
  std::vector<std::vector<u8>> out_wads(src_wads.size());
  size_t page = 0;
  for (auto& [name, new_name] : lines) {
    auto it = src_lines.find(name);
    if (it == src_lines.end()) {
      throw std::runtime_error(fmt::format("[pack-vags] {} isn't in {}", name, src_dir_path));
    }
    u64 packed = pack_vag_name(new_name);
    if (!taken.insert(packed).second) {
      throw std::runtime_error(fmt::format("[pack-vags] {} is already a VAG name", new_name));
    }
    auto [start, stereo] = it->second;
    // the line in each language, and the pages of the longest
    size_t pages = 1;
    std::vector<std::vector<u8>> datas;
    u32 rate = 0;
    for (auto& wad : src_wads) {
      auto header = read_file_range(wad, start, 0x30);
      rate = vag_header_field(header.data(), 16);
      size_t size = 0x30 + vag_header_field(header.data(), 12);
      datas.push_back(read_file_range(wad, start, size));
      pages = std::max(pages, (size + kPage - 1) / kPage);
    }
    u64 rate_index = 12;
    for (u64 r = 0; r < 16; r++) {
      if (kRates[r] == rate) {
        rate_index = r;
      }
    }
    if (page + pages > 0xffff) {
      throw std::runtime_error("[pack-vags] too much audio for a VAG directory");
    }
    entries.push_back(packed | ((u64)(stereo ? 1 : 0) << 42) | (rate_index << 44) |
                      ((u64)page << 48));
    for (size_t i = 0; i < src_wads.size(); i++) {
      auto& out = out_wads[i];
      out.insert(out.end(), datas[i].begin(), datas[i].end());
      out.resize((page + pages) * kPage, 0);
    }
    page += pages;
  }

  // the directory: Jak 3's header (magic, version 2, count), the entries
  std::vector<u8> dir(16 + entries.size() * 8);
  u32 header[4] = {0x41574756, 0x52494444, 2, (u32)entries.size()};
  memcpy(dir.data(), header, 16);
  memcpy(dir.data() + 16, entries.data(), entries.size() * 8);
  file_util::write_binary_file(file_util::get_file_path({task.output.at(0)}), dir.data(),
                               dir.size());
  for (size_t i = 0; i < out_wads.size(); i++) {
    file_util::write_binary_file(file_util::get_file_path({task.output.at(i + 1)}),
                                 out_wads[i].data(), out_wads[i].size());
  }
  return true;
}

AppendSbkTool::AppendSbkTool() : Tool("append-sbk") {}

bool AppendSbkTool::needs_run(const ToolInput& task, const PathMap& path_map) {
  if (task.input.size() < 2) {
    throw std::runtime_error("[append-sbk] Expected at least 2 inputs (base SBK + source dir)");
  }
  bool force = task.input.size() > 2 && task.input.at(2) == "#t";
  std::vector<std::string> deps{task.input.at(0), task.input.at(1)};
  return force || Tool::needs_run({deps, deps, task.output, task.arg}, path_map);
}

bool AppendSbkTool::run(const ToolInput& task, const PathMap&) {
  if (task.input.size() < 2) {
    throw std::runtime_error("[append-sbk] Expected at least 2 inputs (base SBK + source dir)");
  }

  std::vector<std::string> only_names;
  if (task.input.size() > 3) {
    only_names = parse_name_list(m_reader, task.input.at(3));
  }

  sbk::append_sbk_from_dir(file_util::get_file_path({task.input.at(0)}),
                           file_util::get_file_path({task.input.at(1)}),
                           file_util::get_file_path({task.output.at(0)}), only_names);
  return true;
}