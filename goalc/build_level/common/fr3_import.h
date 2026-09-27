#pragma once

// Import already-extracted background data (tfrag/tie/shrub render trees + collision) from
// existing .fr3 files into a custom level. The main use is cross-game: pulling the background of
// a retail level of one game (e.g. Jak 2's Haven City) into a custom level of another game.

#include <string>
#include <unordered_map>
#include <unordered_set>
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
  // TIE and shrub prototypes left out, with the collision of their instances (the source game
  // hides them with prototypes-game-visible-set!, depending on the story). The collision of a
  // TIE prototype is only known if the source fr3 was extracted with the prototype tags, see
  // collision_proto_tag.
  std::unordered_set<std::string> hidden_prototypes;
  // the source game's animated texture slots, by slot (common/texture/texture_slots.h): a draw
  // using a slot gets the slot's source texture (its name without -dest), static
  std::vector<std::string> anim_slot_names;
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
  int anim_slot_draws_mapped = 0;  // of which a static texture of the slot's name was found
  size_t collision_tris = 0;
  size_t collision_tris_clipped = 0;
  size_t hidden_proto_tris = 0;            // render triangles of hidden prototypes left out
  size_t hidden_proto_collision_tris = 0;  // and their collision
  int untagged_collision_levels = 0;       // levels whose collision has no prototype tags
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
  std::unordered_set<u32> m_hidden_tags;  // collision tags of the hidden prototypes
};

}  // namespace fr3_import
