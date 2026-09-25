#include "fr3_import.h"

#include "common/log/log.h"
#include "common/util/Assert.h"
#include "common/util/Serializer.h"
#include "common/util/compress.h"

#include "decompiler/level_extractor/extract_collide_frags.h"

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
  for (const auto& name : m_options.hidden_prototypes) {
    m_hidden_tags.insert(decompiler::collision_proto_tag(name));
  }
}

namespace {
/*!
 * Remove the vis groups of hidden prototypes from a TIE draw. The draw's indices are its runs (each
 * followed by a strip restart) then its plain indices, and its vis groups split that sequence in
 * order: the kept groups become plain indices. Returns the number of triangles removed.
 */
size_t remove_hidden_vis_groups(tfrag3::StripDraw& draw, const std::vector<bool>& hidden_proto) {
  bool any = false;
  for (const auto& grp : draw.vis_groups) {
    any |= grp.tie_proto_idx < hidden_proto.size() && hidden_proto[grp.tie_proto_idx];
  }
  if (!any) {
    return 0;
  }
  std::vector<u32> flat;
  for (const auto& run : draw.runs) {
    for (u32 i = 0; i < run.length; i++) {
      flat.push_back(run.vertex0 + i);
    }
    flat.push_back(UINT32_MAX);
  }
  flat.insert(flat.end(), draw.plain_indices.begin(), draw.plain_indices.end());
  size_t total = 0;
  for (const auto& grp : draw.vis_groups) {
    total += grp.num_inds;
  }
  ASSERT_MSG(total == flat.size(), "fr3 import: TIE vis groups don't match the draw's indices");

  std::vector<u32> kept;
  std::vector<tfrag3::StripDraw::VisGroup> groups;
  size_t pos = 0;
  size_t removed = 0;
  for (const auto& grp : draw.vis_groups) {
    if (grp.tie_proto_idx < hidden_proto.size() && hidden_proto[grp.tie_proto_idx]) {
      removed += grp.num_tris;
      pos += grp.num_inds;
      continue;
    }
    // never let a strip run on into the next kept group
    if (!kept.empty() && kept.back() != UINT32_MAX) {
      kept.push_back(UINT32_MAX);
      groups.back().num_inds++;
    }
    kept.insert(kept.end(), flat.begin() + pos, flat.begin() + pos + grp.num_inds);
    groups.push_back(grp);
    pos += grp.num_inds;
  }
  draw.runs.clear();
  draw.plain_indices = std::move(kept);
  draw.vis_groups = std::move(groups);
  draw.num_triangles -= std::min<u32>(draw.num_triangles, removed);
  return removed;
}

std::vector<bool> hidden_mask(const std::vector<std::string>& proto_names,
                              const std::unordered_set<std::string>& hidden) {
  std::vector<bool> result(proto_names.size());
  for (size_t i = 0; i < proto_names.size(); i++) {
    result[i] = hidden.count(proto_names[i]) != 0;
  }
  return result;
}
}  // namespace

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
        const auto hidden = hidden_mask(out.proto_names, m_options.hidden_prototypes);
        for (auto& draw : out.static_draws) {
          draw.tree_tex_id = remap_texture(src, draw.tree_tex_id, tex_cache);
          m_stats.hidden_proto_tris += remove_hidden_vis_groups(draw, hidden);
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
      const auto hidden = hidden_mask(out.proto_names, m_options.hidden_prototypes);
      for (auto& draw : out.static_draws) {
        draw.tree_tex_id = remap_texture(src, (s32)draw.tree_tex_id, tex_cache);
        if (draw.proto_idx < hidden.size() && hidden[draw.proto_idx]) {
          m_stats.hidden_proto_tris += draw.num_triangles;
          draw.num_indices = 0;
          draw.num_triangles = 0;
        }
      }
      out.has_per_proto_visibility_toggle = false;
      m_stats.shrub_trees++;
    }
  }

  if (m_options.collision) {
    const auto& verts = src.collision.vertices;
    bool tagged = false;
    for (const auto& v : verts) {
      tagged |= v.pad2 != 0;
    }
    bool has_tie = false;
    for (const auto& geom : src.tie_trees) {
      has_tie |= !geom.empty();
    }
    if (has_tie && !tagged && !m_hidden_tags.empty()) {
      m_stats.untagged_collision_levels++;
    }
    for (size_t i = 0; i + 2 < verts.size(); i += 3) {
      if (verts[i].pad2 && m_hidden_tags.count(verts[i].pad2)) {
        m_stats.hidden_proto_collision_tris++;
        continue;
      }
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
