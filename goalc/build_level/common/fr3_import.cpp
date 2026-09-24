#include "fr3_import.h"

#include "common/log/log.h"
#include "common/util/Assert.h"
#include "common/util/Serializer.h"
#include "common/util/compress.h"

#include "fmt/format.h"

namespace fr3_import {

tfrag3::Level load_fr3(const fs::path& path) {
  ASSERT_MSG(fs::exists(path), fmt::format("fr3 import: file not found: {}", path.string()));
  auto data = file_util::read_binary_file(path);
  auto decompressed = compression::decompress_zstd(data.data(), data.size());
  tfrag3::Level result;
  Serializer ser(decompressed.data(), decompressed.size());
  result.serialize(ser);
  return result;
}

Merger::Merger(tfrag3::Level& dst, const Options& options) : m_dst(dst), m_options(options) {
  for (size_t i = 0; i < m_dst.textures.size(); i++) {
    const auto& tex = m_dst.textures[i];
    m_tex_by_key[tex.debug_tpage_name + "/" + tex.debug_name] = (s32)i;
  }
}

s32 Merger::remap_texture(const tfrag3::Level& src, s32 src_idx, std::vector<s32>& cache) {
  if (src_idx < 0) {
    // animated texture slot of the source game. Slot numbers are game-specific, so there is no
    // meaningful equivalent in the destination game. Fall back to the first texture of the level.
    m_stats.anim_slot_draws++;
    src_idx = 0;
  }
  ASSERT((size_t)src_idx < src.textures.size());
  if (cache[src_idx] >= 0) {
    return cache[src_idx];
  }
  const auto& tex = src.textures[src_idx];
  const auto key = tex.debug_tpage_name + "/" + tex.debug_name;
  const auto it = m_tex_by_key.find(key);
  s32 result;
  if (it != m_tex_by_key.end()) {
    result = it->second;
    m_stats.textures_deduplicated++;
  } else {
    result = (s32)m_dst.textures.size();
    auto& added = m_dst.textures.emplace_back(tex);
    // combo ids are the source game's tpage ids: never let them clobber destination textures in
    // the shared texture pool. Level-local lookups by index are all the render trees need.
    added.load_to_pool = false;
    m_tex_by_key[key] = result;
    m_stats.textures_added++;
  }
  cache[src_idx] = result;
  return result;
}

void Merger::merge(const tfrag3::Level& src) {
  m_stats.levels++;
  std::vector<s32> tex_cache(src.textures.size(), -1);

  if (m_options.tfrag) {
    for (int geom = 0; geom < tfrag3::TFRAG_GEOS; geom++) {
      for (const auto& tree : src.tfrag_trees[geom]) {
        // the Jak 3 renderer only draws these kinds. Lowres trees would overlap the normal ones.
        if (tree.kind != tfrag3::TFragmentTreeKind::NORMAL &&
            tree.kind != tfrag3::TFragmentTreeKind::TRANS &&
            tree.kind != tfrag3::TFragmentTreeKind::WATER) {
          m_stats.tfrag_trees_skipped++;
          continue;
        }
        auto& out = m_dst.tfrag_trees[geom].emplace_back(tree);
        for (auto& draw : out.draws) {
          draw.tree_tex_id = remap_texture(src, draw.tree_tex_id, tex_cache);
        }
        m_stats.tfrag_trees++;
      }
    }
  }

  if (m_options.tie) {
    for (int geom = 0; geom < tfrag3::TIE_GEOS; geom++) {
      for (const auto& tree : src.tie_trees[geom]) {
        auto& out = m_dst.tie_trees[geom].emplace_back(tree);
        for (auto& draw : out.static_draws) {
          draw.tree_tex_id = remap_texture(src, draw.tree_tex_id, tex_cache);
        }
        for (auto& draw : out.instanced_wind_draws) {
          draw.tree_tex_id = remap_texture(src, draw.tree_tex_id, tex_cache);
        }
        // proto visibility masks are sent by the GOAL side of the level that owns the protos.
        // A custom level has no such protos, so leave every proto visible.
        out.has_per_proto_visibility_toggle = false;
        m_stats.tie_trees++;
      }
    }
  }

  if (m_options.shrub) {
    for (const auto& tree : src.shrub_trees) {
      auto& out = m_dst.shrub_trees.emplace_back(tree);
      for (auto& draw : out.static_draws) {
        draw.tree_tex_id = remap_texture(src, (s32)draw.tree_tex_id, tex_cache);
      }
      out.has_per_proto_visibility_toggle = false;
      m_stats.shrub_trees++;
    }
  }

  if (m_options.collision) {
    const auto& verts = src.collision.vertices;
    for (size_t i = 0; i + 2 < verts.size(); i += 3) {
      if (m_options.clip_collision) {
        math::Vector3f lo(verts[i].x, verts[i].y, verts[i].z);
        math::Vector3f hi = lo;
        for (int j = 1; j < 3; j++) {
          const math::Vector3f p(verts[i + j].x, verts[i + j].y, verts[i + j].z);
          lo.min_in_place(p);
          hi.max_in_place(p);
        }
        bool outside = false;
        for (int axis = 0; axis < 3; axis++) {
          outside |=
              hi[axis] < m_options.collision_min[axis] || lo[axis] > m_options.collision_max[axis];
        }
        if (outside) {
          m_stats.collision_tris_clipped++;
          continue;
        }
      }
      m_dst.collision.vertices.insert(m_dst.collision.vertices.end(), verts.begin() + i,
                                      verts.begin() + i + 3);
      m_stats.collision_tris++;
    }
  }
}

}  // namespace fr3_import
