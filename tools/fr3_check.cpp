// fr3_check: load a .fr3 file like the game's loader does (decompress, deserialize, unpack) and
// check the references the renderer follows without bounds checks (textures, colors, vertices,
// matrices, bvh nodes). Useful to validate generated or merged custom level fr3 files offline.
//
// usage: fr3_check <path/to/level.fr3> [xmin ymin zmin xmax ymax zmax (meters) | --palettes |
//                                       --draws <name filter> | --textures <name filter> |
//                                       --models <name filter> | --squares <meters>]
//
// --models lists the merc models (actors' skinned meshes) the level carries, one name per line.
// --squares prints, for each square of that size (meters) on x and z holding some, the area (m2,
// seen from above) of the level's collision ground (triangles facing up): "ix iz area" per line,
// ix = floor(x / size). The level port builds its district map from it (which level's ground lies
// under Jak).

#include <cmath>
#include <cstdio>
#include <map>

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

// Average of each time of day palette over the vertices using it: which palettes a level's
// geometry actually lights, to check them against the palette weights its mood sets.
struct PaletteStats {
  double sum[8][3] = {};
  size_t lit[8] = {};
  size_t count = 0;

  void add(const tfrag3::PackedTimeOfDay& colors, u32 color, size_t n) {
    if (color >= colors.color_count) {
      return;
    }
    for (int p = 0; p < 8; p++) {
      bool any = false;
      for (int c = 0; c < 3; c++) {
        const u8 v = colors.read(color, p, c);
        sum[p][c] += (double)v * n;
        any |= v > 8;
      }
      if (any) {
        lit[p] += n;
      }
    }
    count += n;
  }

  void print(const char* what) const {
    if (!count) {
      return;
    }
    fmt::print("{} palettes over {} vertices (average rgb, % of vertices above 8):\n", what,
               count);
    for (int p = 0; p < 8; p++) {
      fmt::print("  {}: {:5.1f} {:5.1f} {:5.1f}  {:5.1f}%\n", p, sum[p][0] / count,
                 sum[p][1] / count, sum[p][2] / count, 100.0 * lit[p] / count);
    }
  }
};

void print_palettes(const tfrag3::Level& lev) {
  PaletteStats tfrag, tie, shrub;
  for (const auto& geom : lev.tfrag_trees) {
    for (const auto& tree : geom) {
      for (const auto& v : tree.packed_vertices.vertices) {
        tfrag.add(tree.colors, v.color_index, 1);
      }
    }
  }
  for (const auto& geom : lev.tie_trees) {
    for (const auto& tree : geom) {
      for (auto c : tree.packed_vertices.color_indices) {
        tie.add(tree.colors, c, 1);
      }
    }
  }
  for (const auto& tree : lev.shrub_trees) {
    for (const auto& grp : tree.packed_vertices.instance_groups) {
      shrub.add(tree.time_of_day_colors, grp.color_index, grp.end_vert - grp.start_vert);
    }
  }
  tfrag.print("tfrag");
  tie.print("tie");
  shrub.print("shrub");
}

// Triangles drawn per texture (and per TIE/shrub prototype) whose name contains a filter: to check
// that some geometry made it into a level, and which prototypes a level has.
void print_draws(const tfrag3::Level& lev, const std::string& filter) {
  auto tex_name = [&](s32 idx) -> std::string {
    if (idx < 0 || idx >= (s32)lev.textures.size()) {
      return fmt::format("<tex {}>", idx);
    }
    return lev.textures[idx].debug_tpage_name + "/" + lev.textures[idx].debug_name;
  };
  std::map<std::string, size_t> tris;
  for (int geom = 0; geom < tfrag3::TFRAG_GEOS; geom++) {
    for (size_t t = 0; t < lev.tfrag_trees[geom].size(); t++) {
      for (const auto& draw : lev.tfrag_trees[geom][t].draws) {
        tris[fmt::format("tfrag[{}][{}] {}", geom, t, tex_name(draw.tree_tex_id))] +=
            draw.num_triangles;
      }
    }
  }
  for (int geom = 0; geom < tfrag3::TIE_GEOS; geom++) {
    for (size_t t = 0; t < lev.tie_trees[geom].size(); t++) {
      const auto& tree = lev.tie_trees[geom][t];
      for (const auto& draw : tree.static_draws) {
        for (const auto& grp : draw.vis_groups) {
          const std::string proto = grp.tie_proto_idx < tree.proto_names.size()
                                        ? tree.proto_names[grp.tie_proto_idx]
                                        : fmt::format("<proto {}>", grp.tie_proto_idx);
          tris[fmt::format("tie[{}][{}] {} {}", geom, t, proto, tex_name(draw.tree_tex_id))] +=
              grp.num_tris;
        }
      }
      for (const auto& draw : tree.instanced_wind_draws) {
        tris[fmt::format("tie[{}][{}] wind {} ({} instance groups)", geom, t,
                         tex_name(draw.tree_tex_id), draw.instance_groups.size())] +=
            draw.num_triangles;
      }
    }
  }
  for (size_t t = 0; t < lev.shrub_trees.size(); t++) {
    const auto& tree = lev.shrub_trees[t];
    for (const auto& draw : tree.static_draws) {
      const std::string proto = draw.proto_idx < tree.proto_names.size()
                                    ? tree.proto_names[draw.proto_idx]
                                    : fmt::format("<proto {}>", draw.proto_idx);
      tris[fmt::format("shrub[{}] {} {}", t, proto, tex_name(draw.tree_tex_id))] +=
          draw.num_triangles;
    }
  }
  for (const auto& [what, n] : tris) {
    if (what.find(filter) != std::string::npos) {
      fmt::print("{:8} {}\n", n, what);
    }
  }
}
}  // namespace

int main(int argc, char** argv) {
  const bool palettes = argc == 3 && std::string(argv[2]) == "--palettes";
  const bool draws = argc == 4 && std::string(argv[2]) == "--draws";
  const bool textures = argc == 4 && std::string(argv[2]) == "--textures";
  const bool models = argc == 4 && std::string(argv[2]) == "--models";
  const bool squares = argc == 4 && std::string(argv[2]) == "--squares";
  if (argc != 2 && argc != 8 && !palettes && !draws && !textures && !models && !squares) {
    fmt::print(
        "usage: fr3_check <path/to/level.fr3> [xmin ymin zmin xmax ymax zmax (meters) | "
        "--palettes | --draws <name filter> | --textures <name filter> | "
        "--models <name filter>]\n");
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
  if (palettes) {
    print_palettes(lev);
    return 0;
  }
  if (draws) {
    print_draws(lev, argv[3]);
    return 0;
  }
  if (textures) {
    for (const auto& tex : lev.textures) {
      const auto name = tex.debug_tpage_name + "/" + tex.debug_name;
      if (name.find(argv[3]) != std::string::npos) {
        fmt::print("{:40} {:4}x{:<4} combo {:#010x} pool {}\n", name, tex.w, tex.h, tex.combo_id,
                   tex.load_to_pool);
      }
    }
    return 0;
  }
  if (models) {
    for (const auto& model : lev.merc_data.models) {
      if (model.name.find(argv[3]) != std::string::npos) {
        fmt::print("{}\n", model.name);
      }
    }
    return 0;
  }
  if (squares) {
    // each ground triangle cut into n * n equal triangles (n from its longest edge), each small
    // triangle's area counted in the square holding its centroid
    const float size = std::stof(argv[3]) * 4096;
    std::map<std::pair<int, int>, double> area;
    const auto& v = lev.collision.vertices;
    for (size_t i = 0; i + 2 < v.size(); i += 3) {
      const float ax = v[i].x, az = v[i].z;
      const float bx = v[i + 1].x - ax, by = v[i + 1].y - v[i].y, bz = v[i + 1].z - az;
      const float cx = v[i + 2].x - ax, cy = v[i + 2].y - v[i].y, cz = v[i + 2].z - az;
      const double nx = by * cz - bz * cy, ny = bz * cx - bx * cz, nz = bx * cy - by * cx;
      const double len = std::sqrt(nx * nx + ny * ny + nz * nz);
      if (len <= 0 || std::abs(ny) < 0.5 * len) {
        continue;  // walls and degenerate triangles
      }
      const float edge =
          std::max({std::hypot(bx, bz), std::hypot(cx, cz), std::hypot(cx - bx, cz - bz)});
      const int n = std::max(1, (int)std::ceil(edge / (size / 4)));
      const double part = std::abs(ny) / 2 / (4096.0 * 4096.0) / (n * n);
      auto add = [&](double s, double t) {
        const double x = ax + s / n * bx + t / n * cx;
        const double z = az + s / n * bz + t / n * cz;
        area[{(int)std::floor(x / size), (int)std::floor(z / size)}] += part;
      };
      for (int a = 0; a < n; a++) {
        for (int b = 0; a + b < n; b++) {
          add(a + 1.0 / 3, b + 1.0 / 3);
          if (a + b < n - 1) {
            add(a + 2.0 / 3, b + 2.0 / 3);
          }
        }
      }
    }
    for (const auto& [sq, a] : area) {
      fmt::print("{} {} {:.1f}\n", sq.first, sq.second, a);
    }
    return 0;
  }

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
  size_t tagged_tris = 0;
  for (size_t i = 0; i < lev.collision.vertices.size(); i += 3) {
    tagged_tris += lev.collision.vertices[i].pad2 != 0;
  }
  fmt::print("collision: {} tris ({} MB), {} tagged with their TIE prototype\n",
             lev.collision.vertices.size() / 3,
             lev.collision.vertices.size() * sizeof(tfrag3::CollisionMesh::Vertex) / (1024 * 1024),
             tagged_tris);

  // world-space extents in meters, to place triggers and doors next to an imported level
  auto print_extent = [](const char* what, const auto& verts) {
    if (verts.empty()) {
      return;
    }
    float lo[3] = {verts[0].x, verts[0].y, verts[0].z};
    float hi[3] = {lo[0], lo[1], lo[2]};
    for (const auto& v : verts) {
      const float p[3] = {v.x, v.y, v.z};
      for (int i = 0; i < 3; i++) {
        lo[i] = std::min(lo[i], p[i]);
        hi[i] = std::max(hi[i], p[i]);
      }
    }
    fmt::print("{} extent (m): [{:.0f} {:.0f} {:.0f}] - [{:.0f} {:.0f} {:.0f}]\n", what,
               lo[0] / 4096, lo[1] / 4096, lo[2] / 4096, hi[0] / 4096, hi[1] / 4096, hi[2] / 4096);
  };
  print_extent("collision", lev.collision.vertices);
  for (const auto& tree : lev.tfrag_trees[0]) {
    print_extent("tfrag", tree.unpacked.vertices);
  }

  // optional box: how much geometry the level has in it (e.g. to find overlaps between levels)
  if (argc == 8) {
    float box[6];
    for (int i = 0; i < 6; i++) {
      box[i] = std::stof(argv[2 + i]) * 4096;
    }
    auto count_in_box = [&](const auto& verts) {
      size_t n = 0;
      for (const auto& v : verts) {
        if (v.x >= box[0] && v.y >= box[1] && v.z >= box[2] && v.x <= box[3] && v.y <= box[4] &&
            v.z <= box[5]) {
          n++;
        }
      }
      return n;
    };
    size_t tfrag_in = 0, tie_in = 0;
    for (const auto& geom : lev.tfrag_trees) {
      for (const auto& tree : geom) {
        tfrag_in += count_in_box(tree.unpacked.vertices);
      }
    }
    for (const auto& tree : lev.tie_trees[0]) {
      tie_in += count_in_box(tree.unpacked.vertices);
    }
    fmt::print("in box: {} collision verts, {} tfrag verts, {} tie verts\n",
               count_in_box(lev.collision.vertices), tfrag_in, tie_in);
  }
  fmt::print("total: {} errors\n", g_errors);
  return g_errors ? 1 : 0;
}
