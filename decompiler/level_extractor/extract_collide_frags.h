#pragma once

#include "BspHeader.h"

#include "common/custom_data/Tfrag3Data.h"

namespace decompiler {

void extract_collide_frags(const level_tools::DrawableTreeCollideFragment* tree,
                           const std::vector<const level_tools::DrawableTreeInstanceTie*>& ties,
                           const Config& config,
                           const std::string& debug_name,
                           tfrag3::Level& out);

void extract_collide_frags(const level_tools::CollideHash& chash,
                           const std::vector<const level_tools::DrawableTreeInstanceTie*>& ties,
                           const Config& config,
                           const std::string& debug_name,
                           const decompiler::DecompilerTypeSystem& dts,
                           tfrag3::Level& out);

void set_vertices_for_tri(tfrag3::CollisionMesh::Vertex* out, const math::Vector4f* in);

// jak 2+: the collision of a TIE prototype's instances is tagged with this in
// CollisionMesh::Vertex::pad2 (0 for the rest of the level's collision). A hash of the prototype
// name, never 0: lets tools drop the collision of prototypes the game hides with
// prototypes-game-visible-set!.
inline u32 collision_proto_tag(const std::string& proto_name) {
  u32 hash = 2166136261u;  // FNV-1a
  for (char c : proto_name) {
    hash = (hash ^ (u8)c) * 16777619u;
  }
  return hash ? hash : 1;
}
}  // namespace decompiler
