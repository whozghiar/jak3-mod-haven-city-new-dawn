// fr3_check: load a .fr3 file like the game's loader does (decompress, deserialize, unpack) and
// check the references the renderer follows without bounds checks (textures, colors, vertices,
// matrices, bvh nodes). Useful to validate generated or merged custom level fr3 files offline.
//
// usage: fr3_check <path/to/level.fr3>

#include <cstdio>

#include "common/custom_data/Tfrag3Data.h"
#include "common/util/FileUtil.h"
#include "common/util/Serializer.h"
#include "common/util/Timer.h"
#include "common/util/compress.h"

#include "fmt/format.h"

namespace {
int g_errors = 0;

void error(const std::string& msg) {
  if (g_errors < 50) {
    fmt::print("ERROR: {}\n", msg);
  }
  g_errors++;
}

// the renderers upload time of day colors into a texture of this width
constexpr u32 kMaxTimeOfDayColors = 8192;

void check_draw_common(const tfrag3::Level& lev,
                       const std::string& where,
                       s32 tex,
                       const std::vector<tfrag3::StripDraw::VisGroup>& groups,
                       size_t num_vis_nodes) {
  if (tex >= (s32)lev.textures.size()) {
    error(fmt::format("{}: texture {} out of range ({})", where, tex, lev.textures.size()));
  }
  for (const auto& grp : groups) {
    if (grp.vis_idx_in_pc_bvh != UINT16_MAX && grp.vis_idx_in_pc_bvh >= num_vis_nodes) {
      error(fmt::format("{}: vis group node {} out of range ({})", where, grp.vis_idx_in_pc_bvh,
                        num_vis_nodes));
      break;
    }
  }
}

void check_tfrag(const tfrag3::Level& lev,
                 const tfrag3::TfragTree& tree,
                 const std::string& where) {
  if (tree.colors.color_count > kMaxTimeOfDayColors) {
    error(fmt::format("{}: {} time of day colors", where, tree.colors.color_count));
  }
  for (const auto& v : tree.packed_vertices.vertices) {
    if (v.cluster_idx >= tree.packed_vertices.cluster_origins.size()) {
      error(fmt::format("{}: cluster {} out of range", where, v.cluster_idx));
      break;
    }
    if (v.color_index >= tree.colors.color_count) {
      error(fmt::format("{}: color {} out of range ({})", where, v.color_index,
                        tree.colors.color_count));
      break;
    }
  }
  const size_t num_verts = tree.packed_vertices.vertices.size();
  for (const auto& draw : tree.draws) {
    check_draw_common(lev, where, draw.tree_tex_id, draw.vis_groups, tree.bvh.vis_nodes.size());
    for (const auto& run : draw.runs) {
      if (run.vertex0 + run.length > num_verts) {
        error(fmt::format("{}: run {}+{} past {} vertices", where, run.vertex0, run.length,
                          num_verts));
        break;
      }
    }
    for (auto idx : draw.plain_indices) {
      if (idx != UINT32_MAX && idx >= num_verts) {
        error(fmt::format("{}: index {} past {} vertices", where, idx, num_verts));
        break;
      }
    }
  }
}

void check_tie(const tfrag3::Level& lev, const tfrag3::TieTree& tree, const std::string& where) {
  const auto& pv = tree.packed_vertices;
  if (tree.colors.color_count > kMaxTimeOfDayColors) {
    error(fmt::format("{}: {} time of day colors", where, tree.colors.color_count));
  }
  size_t total = 0;
  for (const auto& grp : pv.matrix_groups) {
    if (grp.matrix_idx >= (s32)pv.matrices.size()) {
      error(fmt::format("{}: matrix {} out of range ({})", where, grp.matrix_idx,
                        pv.matrices.size()));
    }
    if (grp.end_vert > pv.vertices.size() || grp.start_vert > grp.end_vert) {
      error(fmt::format("{}: matrix group verts {}-{} past {}", where, grp.start_vert, grp.end_vert,
                        pv.vertices.size()));
    }
    total += grp.end_vert - grp.start_vert;
  }
  if (total != pv.color_indices.size()) {
    error(fmt::format("{}: {} unpacked verts but {} color indices", where, total,
                      pv.color_indices.size()));
  }
  for (auto c : pv.color_indices) {
    if (c >= tree.colors.color_count) {
      error(fmt::format("{}: color {} out of range ({})", where, c, tree.colors.color_count));
      break;
    }
  }
  for (const auto& draw : tree.static_draws) {
    check_draw_common(lev, where, draw.tree_tex_id, draw.vis_groups, tree.bvh.vis_nodes.size());
  }
  for (const auto& draw : tree.instanced_wind_draws) {
    if (draw.tree_tex_id >= (s32)lev.textures.size()) {
      error(fmt::format("{}: wind texture {} out of range", where, draw.tree_tex_id));
    }
    for (const auto& grp : draw.instance_groups) {
      if (grp.instance_idx >= tree.wind_instance_info.size()) {
        error(fmt::format("{}: wind instance {} out of range ({})", where, grp.instance_idx,
                          tree.wind_instance_info.size()));
        break;
      }
    }
    for (auto idx : draw.vertex_index_stream) {
      if (idx != UINT32_MAX && idx >= pv.vertices.size()) {
        error(fmt::format("{}: wind index {} past {} proto vertices", where, idx,
                          pv.vertices.size()));
        break;
      }
    }
  }
}
void check_shrub(const tfrag3::Level& lev,
                 const tfrag3::ShrubTree& tree,
                 const std::string& where) {
  if (tree.time_of_day_colors.color_count > kMaxTimeOfDayColors) {
    error(fmt::format("{}: {} time of day colors", where, tree.time_of_day_colors.color_count));
  }
  for (const auto& draw : tree.static_draws) {
    if (draw.tree_tex_id >= lev.textures.size()) {
      error(fmt::format("{}: texture {} out of range ({})", where, draw.tree_tex_id,
                        lev.textures.size()));
    }
    // the shrub renderer indexes its proto visibility mask (sized by proto names) with .at()
    if (draw.proto_idx >= tree.proto_names.size()) {
      error(fmt::format("{}: proto {} out of range ({} names)", where, draw.proto_idx,
                        tree.proto_names.size()));
    }
    if (draw.first_index_index + draw.num_indices > tree.indices.size()) {
      error(fmt::format("{}: draw indices {}+{} past {}", where, draw.first_index_index,
                        draw.num_indices, tree.indices.size()));
    }
  }
}
}  // namespace

int main(int argc, char** argv) {
  if (argc != 2) {
    fmt::print("usage: fr3_check <path/to/level.fr3>\n");
    return 1;
  }
  Timer timer;
  auto data = file_util::read_binary_file(fs::path(argv[1]));
  auto decompressed = compression::decompress_zstd(data.data(), data.size());
  tfrag3::Level lev;
  Serializer ser(decompressed.data(), decompressed.size());
  lev.serialize(ser);
  fmt::print("{}: {} textures, loaded in {:.2f}s ({} MB uncompressed)\n", lev.level_name,
             lev.textures.size(), timer.getSeconds(), decompressed.size() / (1024 * 1024));

  for (size_t i = 0; i < lev.textures.size(); i++) {
    const auto& tex = lev.textures[i];
    if (tex.data.size() != (size_t)tex.w * tex.h) {
      error(fmt::format("texture {} ({}) has {} pixels for {}x{}", i, tex.debug_name,
                        tex.data.size(), tex.w, tex.h));
    }
  }

  for (int geom = 0; geom < tfrag3::TFRAG_GEOS; geom++) {
    for (size_t i = 0; i < lev.tfrag_trees[geom].size(); i++) {
      check_tfrag(lev, lev.tfrag_trees[geom][i], fmt::format("tfrag[{}][{}]", geom, i));
    }
  }
  size_t tie_matrices = 0;
  for (int geom = 0; geom < tfrag3::TIE_GEOS; geom++) {
    for (size_t i = 0; i < lev.tie_trees[geom].size(); i++) {
      check_tie(lev, lev.tie_trees[geom][i], fmt::format("tie[{}][{}]", geom, i));
      tie_matrices += lev.tie_trees[geom][i].packed_vertices.matrices.size();
    }
  }
  for (size_t i = 0; i < lev.shrub_trees.size(); i++) {
    check_shrub(lev, lev.shrub_trees[i], fmt::format("shrub[{}]", i));
  }
  if (lev.collision.vertices.size() % 3) {
    error("collision vertex count is not a multiple of 3");
  }
  fmt::print("static checks done: {} errors\n", g_errors);

  // same unpack as the game's loader thread
  timer.start();
  size_t tie_verts = 0, tie_inds = 0, tfrag_verts = 0, tfrag_inds = 0;
  for (auto& geom : lev.tie_trees) {
    for (auto& tree : geom) {
      tree.unpack();
      tie_verts += tree.unpacked.vertices.size();
      tie_inds += tree.unpacked.indices.size();
    }
  }
  for (auto& geom : lev.tfrag_trees) {
    for (auto& tree : geom) {
      tree.unpack();
      tfrag_verts += tree.unpacked.vertices.size();
      tfrag_inds += tree.unpacked.indices.size();
    }
  }
  size_t shrub_verts = 0;
  for (size_t i = 0; i < lev.shrub_trees.size(); i++) {
    auto& tree = lev.shrub_trees[i];
    tree.unpack();
    shrub_verts += tree.unpacked.vertices.size();
    // shrub indices point into the unpacked (per-instance) vertices
    for (auto idx : tree.indices) {
      if (idx != UINT32_MAX && idx >= tree.unpacked.vertices.size()) {
        error(fmt::format("shrub[{}]: index {} past {} vertices", i, idx,
                          tree.unpacked.vertices.size()));
        break;
      }
    }
  }
  fmt::print("unpack done in {:.2f}s\n", timer.getSeconds());
  fmt::print("tie: {} matrices, {} verts ({} MB), {} indices ({} MB)\n", tie_matrices, tie_verts,
             tie_verts * sizeof(tfrag3::PreloadedVertex) / (1024 * 1024), tie_inds,
             tie_inds * 4 / (1024 * 1024));
  fmt::print("tfrag: {} verts ({} MB), {} indices ({} MB)\n", tfrag_verts,
             tfrag_verts * sizeof(tfrag3::PreloadedVertex) / (1024 * 1024), tfrag_inds,
             tfrag_inds * 4 / (1024 * 1024));
  fmt::print("shrub: {} verts\n", shrub_verts);
  fmt::print("collision: {} tris ({} MB)\n", lev.collision.vertices.size() / 3,
             lev.collision.vertices.size() * sizeof(tfrag3::CollisionMesh::Vertex) / (1024 * 1024));
  fmt::print("total: {} errors\n", g_errors);
  return g_errors ? 1 : 0;
}
