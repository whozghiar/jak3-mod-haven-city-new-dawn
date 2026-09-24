#pragma once

#include "Tie.h"

#include "common/custom_data/Tfrag3Data.h"
#include "common/util/gltf_util.h"

#include "goalc/build_level/common/gltf_mesh_extract.h"
#include "goalc/data_compiler/DataObjectGenerator.h"

void tie_from_gltf(const gltf_mesh_extract::TieOutput& mesh_extract_out,
                   std::vector<tfrag3::TieTree>& out_pc);

class DrawableTreeInstanceTie {
 public:
  // Jak 3's draw-drawable-tree-instance-tie reads `data[length - 1]` and the proxy's
  // prototype-max-qwc unconditionally: an empty tree must then have one empty instance array and
  // a full-size proxy, or the draw dereferences garbage.
  explicit DrawableTreeInstanceTie(bool with_empty_instance_array = false)
      : m_with_empty_instance_array(with_empty_instance_array) {}
  size_t add_to_object_file(DataObjectGenerator& gen) const;

 private:
  bool m_with_empty_instance_array = false;
};