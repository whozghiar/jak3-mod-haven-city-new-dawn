#include "build_level.h"

#include "decompiler/extractor/extractor_util.h"
#include "decompiler/level_extractor/extract_collide_frags.h"
#include "decompiler/level_extractor/extract_merc.h"
#include "goalc/build_level/collide/jak3/collide.h"
#include "goalc/build_level/common/Tfrag.h"
#include "goalc/build_level/common/fr3_import.h"
#include "goalc/build_level/jak3/Entity.h"
#include "goalc/build_level/jak3/FileInfo.h"
#include "goalc/build_level/jak3/LevelFile.h"

namespace jak3 {
bool run_build_level(const std::string& input_file,
                     const std::string& bsp_output_file,
                     const std::string& output_prefix,
                     bool gen_fr3) {
  auto level_json = parse_commented_json(
      file_util::read_text_file(file_util::get_file_path({input_file})), input_file);
  LevelFile file;                   // GOAL level file
  tfrag3::Level pc_level;           // PC level file
  gltf_util::TexturePool tex_pool;  // pc level texture pool

  // process input mesh from blender. Optional when the background comes from "import_fr3".
  gltf_mesh_extract::Output mesh_extract_out;
  if (level_json.contains("gltf_file")) {
    gltf_mesh_extract::Input mesh_extract_in;
    mesh_extract_in.filename =
        file_util::get_file_path({level_json.at("gltf_file").get<std::string>()});
    mesh_extract_in.auto_wall_enable = level_json.value("automatic_wall_detection", true);
    mesh_extract_in.double_sided_collide = level_json.value("double_sided_collide", false);
    mesh_extract_in.auto_wall_angle = level_json.value("automatic_wall_angle", 30.0);
    mesh_extract_in.tex_pool = &tex_pool;
    gltf_mesh_extract::extract(mesh_extract_in, mesh_extract_out);
  }

  // add stuff to the GOAL level structure
  file.info = make_file_info_for_level(fs::path(input_file).filename().string());
  // all vis
  // drawable trees
  // pat
  // texture remap
  // texture ids
  // unk zero
  // name
  file.name = level_json.at("long_name").get<std::string>();
  ASSERT_MSG(file.name.size() <= 10,
             fmt::format("long_name over 10 characters ({} characters): '{}'", file.name.size(),
                         file.name));
  // nick
  file.nickname = level_json.at("nickname").get<std::string>();
  // vis infos
  // actors
  auto dts = decompiler::DecompilerTypeSystem(GameVersion::Jak3);
  dts.parse_enum_defs({"decompiler", "config", "jak3", "all-types.gc"});
  std::vector<EntityActor> actors;
  add_actors_from_json(level_json.at("actors"), actors, level_json.value("base_id", 1234), dts);
  std::sort(actors.begin(), actors.end(), [](auto& a, auto& b) { return a.aid < b.aid; });
  auto duplicates = std::adjacent_find(actors.begin(), actors.end(),
                                       [](auto& a, auto& b) { return a.aid == b.aid; });
  ASSERT_MSG(duplicates == actors.end(),
             fmt::format("Actor IDs must be unique. Found at least two actors with ID {}",
                         duplicates->aid));
  file.actors = std::move(actors);
  // actor groups
  if (level_json.contains("actor_groups") && !level_json.at("actor_groups").empty()) {
    add_actor_groups_from_json(level_json.at("actor_groups"), file.actors, file.actor_groups, 0);
  }
  // cameras: fixed cameras, e.g. taken from a Jak 2 level's <level>-cameras.json dump. Their ids
  // follow the actors'.
  if (level_json.contains("cameras")) {
    u32 base_aid = level_json.value("base_id", 1234) + (u32)file.actors.size() + 1;
    for (const auto& actor : file.actors) {
      base_aid = std::max(base_aid, actor.aid + 1);
    }
    add_cameras_from_json(level_json.at("cameras"), file.cameras, base_aid, dts);
    for (const auto& cam : file.cameras) {
      ASSERT_MSG(std::none_of(file.actors.begin(), file.actors.end(),
                              [&](const EntityActor& a) { return a.aid == cam.aid; }),
                 fmt::format("camera {} has the id {} of an actor", cam.name, cam.aid));
    }
  }
  // nav_data: a DataBlob holding the level's city-level-info and nav meshes (for havenj2, Jak 2's
  // city's, made by custom_assets/jak3/levels/havenj2/gen_havenj2_nav.py). The nav meshes keep
  // their ids (the nav graph refers to them), which must not be an actor's.
  if (level_json.contains("nav_data")) {
    file.nav_data = DataBlob::from_json_file(level_json.at("nav_data").get<std::string>());
    int meshes = 0;
    for (const auto& [name, byte] : file.nav_data->roots) {
      if (name.rfind("nav-mesh-", 0) == 0) {
        meshes++;
        // entity aid: 48 bytes from the type tag, the root being 4 bytes after it
        const u32 aid = file.nav_data->words.at((byte + 44) / 4);
        ASSERT_MSG(std::none_of(file.actors.begin(), file.actors.end(),
                                [&](const EntityActor& a) { return a.aid == aid; }),
                   fmt::format("nav mesh {} has the id {} of an actor", name, aid));
      }
    }
    lg::info("nav data: {} KB, {} nav meshes", file.nav_data->words.size() * 4 / 1024, meshes);
  }
  // nodes
  // regions
  auto region_trees = level_json.value("region_trees", nlohmann::json::object());
  if (level_json.contains("region_tree_files")) {
    // region trees kept in separate (usually generated) json files. Their regions are appended to
    // the tree of the same name, whose bsphere must then encompass them.
    for (const auto& path : level_json.at("region_tree_files").get<std::vector<std::string>>()) {
      const auto extra =
          parse_commented_json(file_util::read_text_file(file_util::get_file_path({path})), path);
      for (const auto& [name, tree] : extra.items()) {
        if (!region_trees.contains(name) || region_trees.at(name).empty()) {
          region_trees[name] = tree;
        } else {
          for (const auto& region : tree.at("regions")) {
            region_trees[name]["regions"].push_back(region);
          }
        }
      }
    }
  }
  if (!region_trees.empty()) {
    file.region_array.entities = &file.actors;
    file.region_array.actor_groups = &file.actor_groups;
    fill_region_trees(file.region_trees, file.regions, file.region_array, region_trees,
                      level_json.value("base_region_id", 0));
  }
  // subdivs
  // actor birth
  for (size_t i = 0; i < file.actors.size(); i++) {
    file.actor_birth_order.push_back(i);
  }

  // add stuff to the PC level structure
  pc_level.level_name = file.name;

  // TFRAG
  tfrag_from_gltf(mesh_extract_out.tfrag, pc_level.tfrag_trees[0]);

  // TIE
  if (!mesh_extract_out.tie.base_draws.empty()) {
    tie_from_gltf(mesh_extract_out.tie, pc_level.tie_trees[0]);
  }

  pc_level.textures = std::move(tex_pool.textures_by_idx);

  // IMPORTED BACKGROUND (render trees + collision from existing .fr3 files, possibly of another
  // game). Collision vertices land in pc_level.collision, with their original pat.
  if (level_json.contains("import_fr3")) {
    const auto& imp = level_json.at("import_fr3");
    fr3_import::Options opts;
    opts.tfrag = imp.value("tfrag", true);
    opts.tie = imp.value("tie", true);
    opts.shrub = imp.value("shrub", true);
    opts.collision = imp.value("collision", true);
    if (imp.contains("collision_bounds")) {
      // [xmin, ymin, zmin, xmax, ymax, zmax], in meters
      const auto b = imp.at("collision_bounds").get<std::vector<float>>();
      ASSERT_MSG(b.size() == 6, "import_fr3.collision_bounds must have 6 values");
      opts.clip_collision = true;
      opts.collision_min = math::Vector3f(b[0], b[1], b[2]) * 4096.f;
      opts.collision_max = math::Vector3f(b[3], b[4], b[5]) * 4096.f;
    }
    // prototypes the source game hides in the story state kept, e.g. "ctyp-statue-rubble-a.mb"
    for (const auto& name : imp.value("hide_prototypes", std::vector<std::string>{})) {
      opts.hidden_prototypes.insert(name);
    }
    const auto game = imp.value("game", std::string("jak2"));
    fr3_import::Merger merger(pc_level, opts);
    for (const auto& lev : imp.at("levels").get<std::vector<std::string>>()) {
      const auto path = file_util::get_jak_project_dir() / "out" / game / "fr3" / (lev + ".fr3");
      lg::info("fr3 import: merging {}", path.string());
      merger.merge(fr3_import::load_fr3(path));
    }
    const auto& st = merger.stats();
    lg::info(
        "fr3 import: {} levels, {} tfrag trees ({} skipped), {} tie trees, {} shrub trees, {} "
        "textures ({} deduplicated), {} collision tris ({} clipped)",
        st.levels, st.tfrag_trees, st.tfrag_trees_skipped, st.tie_trees, st.shrub_trees,
        st.textures_added, st.textures_deduplicated, st.collision_tris, st.collision_tris_clipped);
    if (st.anim_slot_draws) {
      lg::warn("fr3 import: {} draws used a source-game animated texture slot, using a fallback",
               st.anim_slot_draws);
    }
    if (!opts.hidden_prototypes.empty()) {
      lg::info("fr3 import: hidden prototypes: {} triangles, {} collision triangles",
               st.hidden_proto_tris, st.hidden_proto_collision_tris);
    }
    if (st.untagged_collision_levels) {
      lg::warn(
          "fr3 import: {} levels have no prototype tags on their collision (extracted by an older "
          "decompiler): the collision of hidden prototypes is kept",
          st.untagged_collision_levels);
    }
    // imported trees keep their bvh vis nodes: mark every vis id visible (2048 bytes is the size
    // of a level's vis-bits), frustum culling still applies.
    file.all_visibile_list.bytes.assign(2048, 0xff);
  }

  // SPRITE TEXTURES: textures taken from .fr3 files (possibly of another game) and given to the PC
  // texture pool as a texture page of their own, for sprites and particles: the level's GOAL code
  // makes a texture-page with that id at runtime, whose upload maps each texture to a VRAM slot.
  // Entry i of the list is texture i of the page: [source level, source tpage, texture name].
  if (level_json.contains("sprite_textures")) {
    const auto& st = level_json.at("sprite_textures");
    const u32 page = st.at("page").get<u32>();
    ASSERT_MSG(page > 0 && page < 4096, "sprite_textures.page must be a 12 bit texture page id");
    const auto game = st.value("game", std::string("jak2"));
    std::unordered_map<std::string, tfrag3::Level> sources;
    const auto& list = st.at("textures");
    ASSERT_MSG(list.size() < 4096, "sprite_textures: too many textures for one page");
    for (size_t i = 0; i < list.size(); i++) {
      const auto src_level = list[i].at(0).get<std::string>();
      const auto src_tpage = list[i].at(1).get<std::string>();
      const auto src_name = list[i].at(2).get<std::string>();
      // an entry may name its own game: [level, tpage, name, game]
      const auto src_game = list[i].size() > 3 ? list[i].at(3).get<std::string>() : game;
      const auto src_key = src_game + "/" + src_level;
      auto src = sources.find(src_key);
      if (src == sources.end()) {
        const auto path =
            file_util::get_jak_project_dir() / "out" / src_game / "fr3" / (src_level + ".fr3");
        src = sources.emplace(src_key, fr3_import::load_fr3(path)).first;
      }
      const tfrag3::Texture* found = nullptr;
      for (const auto& tex : src->second.textures) {
        if (tex.debug_tpage_name == src_tpage && tex.debug_name == src_name) {
          found = &tex;
          break;
        }
      }
      ASSERT_MSG(found, fmt::format("sprite_textures: no texture {}/{} in {}.fr3", src_tpage,
                                    src_name, src_level));
      auto& out = pc_level.textures.emplace_back(*found);
      out.combo_id = (page << 16) | (u32)i;
      out.load_to_pool = true;
    }
    lg::info("sprite textures: {} textures as texture page {}", list.size(), page);
  }

  // GOAL-side drawable trees. The PC renderer draws every fr3 tree of a kind as soon as the level
  // sends one tree of that kind, so a single empty tree per kind is enough.
  auto has_tfrag_kind = [&](tfrag3::TFragmentTreeKind kind) {
    for (const auto& geom : pc_level.tfrag_trees) {
      for (const auto& tree : geom) {
        if (tree.kind == kind) {
          return true;
        }
      }
    }
    return false;
  };
  if (has_tfrag_kind(tfrag3::TFragmentTreeKind::NORMAL) || !level_json.contains("import_fr3")) {
    file.drawable_trees.tfrags.emplace_back("drawable-tree-tfrag", "drawable-inline-array-tfrag");
  }
  if (has_tfrag_kind(tfrag3::TFragmentTreeKind::TRANS)) {
    file.drawable_trees.tfrags.emplace_back("drawable-tree-tfrag-trans",
                                            "drawable-inline-array-tfrag-trans");
  }
  if (has_tfrag_kind(tfrag3::TFragmentTreeKind::WATER)) {
    file.drawable_trees.tfrags.emplace_back("drawable-tree-tfrag-water",
                                            "drawable-inline-array-tfrag-water");
  }
  bool has_tie = false;
  for (const auto& geom : pc_level.tie_trees) {
    has_tie |= !geom.empty();
  }
  if (has_tie) {
    file.drawable_trees.ties.emplace_back(true);
  }
  if (!pc_level.shrub_trees.empty()) {
    file.drawable_trees.shrubs.emplace_back();
  }

  // COLLIDE
  std::vector<jak3::CollideFace> collide_faces;
  for (const auto& face : mesh_extract_out.collide.faces) {
    auto& out = collide_faces.emplace_back();
    for (int i = 0; i < 3; i++) {
      out.v[i] = face.v[i];
    }
    out.pat = jak3_pat(face.pat);
  }
  // imported collision: jak 2 and jak 3 share the pat-surface bit layout, so the value is kept.
  const auto& imported_verts = pc_level.collision.vertices;
  for (size_t i = 0; i + 2 < imported_verts.size(); i += 3) {
    auto& out = collide_faces.emplace_back();
    for (int j = 0; j < 3; j++) {
      const auto& v = imported_verts[i + j];
      out.v[j] = math::Vector3f(v.x, v.y, v.z);
    }
    out.pat.val = imported_verts[i].pat;
  }

  if (collide_faces.empty()) {
    lg::error("No collision geometry was found");
  } else {
    file.collide_hash = construct_collide_hash(collide_faces);
    // for collision renderer
    for (auto& face : mesh_extract_out.collide.faces) {
      math::Vector4f verts[3];
      for (int i = 0; i < 3; i++) {
        verts[i].x() = face.v[i].x();
        verts[i].y() = face.v[i].y();
        verts[i].z() = face.v[i].z();
        verts[i].w() = 1.f;
      }
      tfrag3::CollisionMesh::Vertex out_verts[3];
      decompiler::set_vertices_for_tri(out_verts, verts);
      for (auto& out : out_verts) {
        out.pat = face.pat.val;
        pc_level.collision.vertices.push_back(out);
      }
    }
  }

  // Save the GOAL level
  auto result = file.save_object_file();
  lg::print("Level bsp file size {} bytes\n", result.size());
  auto save_path = file_util::get_jak_project_dir() / bsp_output_file;
  file_util::create_dir_if_needed_for_file(save_path);
  lg::print("Saving to {}\n", save_path.string());
  file_util::write_binary_file(save_path, result.data(), result.size());

  // Add textures and models
  // TODO remove hardcoded config settings
  if (gen_fr3 && ((level_json.contains("art_groups") && !level_json.at("art_groups").empty()) ||
                  (level_json.contains("textures") && !level_json.at("textures").empty()))) {
    lg::info("Looking for ISO path...");
    const auto iso_folder = file_util::get_iso_dir_for_game(GameVersion::Jak3);
    lg::info("Found ISO path: {}", iso_folder.string());

    if (iso_folder.empty() || !fs::exists(iso_folder)) {
      lg::warn("Could not locate ISO path!");
      return false;
    }

    // Look for iso build info if it's available, otherwise default to ntsc_v1
    const auto version_info = get_version_info_or_default(iso_folder);

    decompiler::Config config;
    try {
      config = decompiler::read_config_file(
          file_util::get_jak_project_dir() / "decompiler/config/jak3/jak3_config.jsonc",
          version_info.decomp_config_version,
          R"({"decompile_code": false, "find_functions": false, "levels_extract": true, "allowed_objects": [], "save_texture_pngs": false})");
    } catch (const std::exception& e) {
      lg::error("Failed to parse config: {}", e.what());
      return false;
    }

    std::vector<fs::path> dgos, objs;
    for (const auto& dgo_name : config.dgo_names) {
      dgos.push_back(iso_folder / dgo_name);
    }

    for (const auto& obj_name : config.object_file_names) {
      objs.push_back(iso_folder / obj_name);
    }

    decompiler::ObjectFileDB db(dgos, fs::path(config.obj_file_name_map_file), objs, {}, {}, {},
                                config);

    // need to process link data for tpages
    db.process_link_data(config);

    decompiler::TextureDB tex_db;
    auto textures_out = file_util::get_jak_project_dir() / "decompiler_out/jak3/textures";
    file_util::create_dir_if_needed(textures_out);
    db.process_tpages(tex_db, textures_out, config, "");
    auto replacements_path = file_util::get_jak_project_dir() / "custom_assets" /
                             game_version_names[config.game_version] / "texture_replacements";
    if (fs::exists(replacements_path)) {
      tex_db.replace_textures(replacements_path);
    }

    // add textures
    if (level_json.contains("textures") && !level_json.at("textures").empty()) {
      std::vector<std::string> processed_textures;
      std::vector<std::string> wanted_texs =
          level_json.at("textures").get<std::vector<std::string>>();
      // first check the texture is not already in the level
      for (auto& level_tex : pc_level.textures) {
        if (std::find(wanted_texs.begin(), wanted_texs.end(), level_tex.debug_name) !=
            wanted_texs.end()) {
          processed_textures.push_back(level_tex.debug_name);
        }
      }

      // then add
      for (auto& [id, tex] : tex_db.textures) {
        for (auto& tex0 : wanted_texs) {
          if (std::find(processed_textures.begin(), processed_textures.end(), tex.name) !=
              processed_textures.end()) {
            continue;
          }
          if (tex.name == tex0) {
            lg::info("custom level: adding texture {} from tpage {} ({})", tex.name, tex.page,
                     tex_db.tpage_names.at(tex.page));
            pc_level.textures.push_back(make_texture(id, tex_db, true));
            processed_textures.push_back(tex.name);
          }
        }
      }
    }

    // find all art groups used by the custom level in other dgos
    if (gen_fr3 && level_json.contains("art_groups") && !level_json.at("art_groups").empty()) {
      // shared by every DGO: an art group is extracted from the first DGO that has it (Jak 3 ships
      // com-airlock-outer-ag in 15 of them)
      std::vector<std::string> processed_art_groups;
      for (auto& dgo : config.dgo_names) {
        // remove "DGO/" prefix
        const auto& dgo_name = dgo.substr(4);
        const auto& files = db.obj_files_by_dgo.at(dgo_name);
        auto art_groups =
            find_art_groups(processed_art_groups,
                            level_json.at("art_groups").get<std::vector<std::string>>(), files);
        auto tex_remap = decompiler::extract_tex_remap(db, dgo_name);
        for (const auto& ag : art_groups) {
          if (ag.name.length() > 3 && !ag.name.compare(ag.name.length() - 3, 3, "-ag")) {
            const auto& ag_file = db.lookup_record(ag);
            lg::print("custom level: extracting art group {}\n", ag_file.name_in_dgo);
            decompiler::MercSwapInfo info;
            decompiler::extract_merc(ag_file, tex_db, db.dts, tex_remap, pc_level, false,
                                     db.version(), info);
          }
        }
      }
    }
  }

  // add custom models to fr3
  if (gen_fr3 && level_json.contains("custom_models") && !level_json.at("custom_models").empty()) {
    auto models = level_json.at("custom_models").get<std::vector<std::string>>();
    for (auto& name : models) {
      add_model_to_level(GameVersion::Jak3, name, pc_level);
    }
  }

  // Save the PC level
  if (gen_fr3) {
    save_pc_data(file.name, pc_level,
                 file_util::get_jak_project_dir() / "out" / output_prefix / "fr3");
  }
  return true;
}
}  // namespace jak3
