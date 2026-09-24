#pragma once

// Import already-extracted background data (tfrag/tie/shrub render trees + collision) from
// existing .fr3 files into a custom level. The main use is cross-game: pulling the background of
// a retail level of one game (e.g. Jak 2's Haven City) into a custom level of another game.

#include <string>
#include <unordered_map>
#include <vector>

#include "common/custom_data/Tfrag3Data.h"
#include "common/math/Vector.h"
#include "common/util/FileUtil.h"

namespace fr3_import {

struct Options {
  bool tfrag = true;
  bool tie = true;
  bool shrub = true;
  bool collision = true;
  // Optional clip box for imported collision, in game units. Triangles whose bounding box misses it
  // are dropped: unreachable backdrop collision (distant mountains) would otherwise inflate the
  // collide hash grid for nothing.
  bool clip_collision = false;
  math::Vector3f collision_min = math::Vector3f::zero();
  math::Vector3f collision_max = math::Vector3f::zero();
};

struct Stats {
  int levels = 0;
  int textures_added = 0;
  int textures_deduplicated = 0;
  int tfrag_trees = 0;
  int tfrag_trees_skipped = 0;
  int tie_trees = 0;
  int shrub_trees = 0;
  int anim_slot_draws = 0;
  size_t collision_tris = 0;
  size_t collision_tris_clipped = 0;
};

tfrag3::Level load_fr3(const fs::path& path);

/*!
 * Appends render trees, textures and collision of source levels into a destination level.
 * Textures are deduplicated by tpage + name, so importing adjacent levels that share tpages
 * doesn't multiply texture memory.
 */
class Merger {
 public:
  Merger(tfrag3::Level& dst, const Options& options);
  void merge(const tfrag3::Level& src);
  const Stats& stats() const { return m_stats; }

 private:
  s32 remap_texture(const tfrag3::Level& src, s32 src_idx, std::vector<s32>& cache);

  tfrag3::Level& m_dst;
  Options m_options;
  Stats m_stats;
  std::unordered_map<std::string, s32> m_tex_by_key;
};

}  // namespace fr3_import
