#include "LevelFile.h"

#include "goalc/data_compiler/DataObjectGenerator.h"

namespace jak3 {
size_t DrawableTreeArray::add_to_object_file(DataObjectGenerator& gen) const {
  /*
   (deftype drawable-tree-array (drawable-group)
    ((trees drawable-tree 1 :offset 32 :score 100))
    :flag-assert #x1200000024
    )
    (deftype drawable-group (drawable)
      ((length  int16       :offset 6)
       (data    drawable 1  :offset-assert 32)
       )
      (:methods
        (new (symbol type int) _type_)
        )
      :flag-assert #x1200000024
      )
   */
  gen.align_to_basic();
  gen.add_type_tag("drawable-tree-array");
  size_t result = gen.current_offset_bytes();
  int num_trees = 0;
  num_trees += tfrags.size();
  num_trees += ties.size();
  num_trees += shrubs.size();
  gen.add_word(num_trees << 16);
  gen.add_word(0);
  gen.add_word(0);

  gen.add_word(0);
  gen.add_word(0);
  gen.add_word(0);
  gen.add_word(0);

  // todo add trees...

  if (num_trees == 0) {
    gen.add_word(0);  // the one at the end.
  } else {
    int tree_word = (int)gen.current_offset_bytes() / 4;
    for (int i = 0; i < num_trees; i++) {
      gen.add_word(0);
    }

    for (auto& tfrag : tfrags) {
      // gen.set_word(tree_word++, tfrag.add_to_object_file(gen));
      gen.link_word_to_byte(tree_word++, tfrag.add_to_object_file(gen));
    }

    for (auto& tie : ties) {
      gen.link_word_to_byte(tree_word++, tie.add_to_object_file(gen));
    }

    for (auto& shrub : shrubs) {
      gen.link_word_to_byte(tree_word++, shrub.add_to_object_file(gen));
    }
  }

  return result;
}

size_t DrawableTreeInstanceShrub::add_to_object_file(DataObjectGenerator& gen) const {
  /*
   (deftype prototype-array-shrub-info (basic)
     ((prototype-inline-array-shrub prototype-inline-array-shrub)   ;; 4
      (wind-vectors                 uint32)                         ;; 8
      (wind-count                   int32)))                        ;; 12
   (deftype drawable-tree-instance-shrub (drawable-tree)
     ((info         prototype-array-shrub-info :offset 8)
      (colors-added time-of-day-palette        :offset 12)))       ;; data[0] at 32
   */
  // empty prototype array (length 0) and empty instance array (one 80-byte instance slot)
  const size_t protos = add_empty_dia("prototype-inline-array-shrub", gen, 0x40);
  const size_t instances = add_empty_dia("drawable-inline-array-instance-shrub", gen, 0x74);

  gen.align_to_basic();
  gen.add_type_tag("prototype-array-shrub-info");  // 0
  const size_t info = gen.current_offset_bytes();
  gen.link_word_to_byte(gen.add_word(0), protos);  // 4
  gen.add_word(0);                                 // 8 wind-vectors
  gen.add_word(0);                                 // 12 wind-count

  gen.align_to_basic();
  gen.add_type_tag("drawable-tree-instance-shrub");  // 0
  const size_t result = gen.current_offset_bytes();
  gen.add_word(1 << 16);                         // 4 (id = 0, length = 1)
  gen.link_word_to_byte(gen.add_word(0), info);  // 8 info
  for (int i = 0; i < 5; i++) {
    gen.add_word(0);  // 12 colors-added, 16 bsphere
  }
  const size_t slot = gen.add_word(0);  // 32 data[0]
  ASSERT(slot * 4 - result == 28);
  gen.link_word_to_byte(slot, instances);
  return result;
}

size_t generate_u32_array(const std::vector<u32>& array, DataObjectGenerator& gen) {
  gen.align(4);
  size_t result = gen.current_offset_bytes();
  for (auto& entry : array) {
    gen.add_word(entry);
  }
  return result;
}

std::vector<u8> LevelFile::save_object_file() {
  DataObjectGenerator gen;
  gen.add_type_tag("bsp-header");

  // add blank space for the bsp-header
  while (gen.words() < 100) {
    gen.add_word(0);
  }

  //(info                   file-info                        :offset          4)
  auto file_info_slot = info.add_to_object_file(gen);
  gen.link_word_to_byte(1, file_info_slot);

  //(bsphere                vector :inline                   :offset-assert  16)
  //(all-visible-list       (pointer uint8)                  :offset-assert  32)
  //(visible-list-length    int16                            :offset-assert  36)
  //(extra-vis-list-length  int16                            :offset-assert  38)
  // A level without vis-info gets its vis-bits from this list every frame (cam-update.gc). Geometry
  // built from a glb doesn't use vis nodes, but geometry imported from another level's fr3 keeps
  // its bvh nodes, which are culled when their vis bit is 0.
  if (!all_visibile_list.bytes.empty()) {
    const auto& bytes = all_visibile_list.bytes;
    ASSERT(bytes.size() % 16 == 0 && bytes.size() <= 2048);
    gen.align(4);
    const size_t list = gen.current_offset_bytes();
    for (size_t i = 0; i < bytes.size(); i += 4) {
      gen.add_word(bytes[i] | (bytes[i + 1] << 8) | (bytes[i + 2] << 16) | (bytes[i + 3] << 24));
    }
    gen.link_word_to_byte(32 / 4, list);
    gen.set_word(36 / 4, bytes.size());  // extra-vis-list-length = 0
  }
  //(drawable-trees         drawable-tree-array              :offset-assert  40)
  gen.link_word_to_byte(40 / 4, drawable_trees.add_to_object_file(gen));
  //(pat                    pointer                          :offset-assert  44)
  //(pat-length             int32                            :offset-assert  48)
  //(texture-remap-table    (pointer uint64)                 :offset-assert  52)
  //(texture-remap-table-len int32                           :offset-assert  56)
  //(texture-ids            (pointer texture-id)             :offset-assert  60)
  //(texture-page-count     int32                            :offset-assert  64)
  //(unknown-basic          basic                            :offset-assert  68)
  //(name                   symbol                           :offset-assert  72)
  gen.link_word_to_symbol(name, 72 / 4);
  //(nickname               symbol                           :offset-assert  76)
  gen.link_word_to_symbol(nickname, 76 / 4);
  //(vis-info               level-vis-info                8  :offset-assert  80)
  //(actors                 drawable-inline-array-actor      :offset-assert 112)
  gen.link_word_to_byte(112 / 4, generate_inline_array_actors(gen, actors));
  //(cameras                (array entity-camera)            :offset-assert 116)
  //(nodes                  (inline-array bsp-node)          :offset-assert 120)
  //(level                  level                            :offset-assert 124)
  //(current-leaf-idx       uint16                           :offset-assert 128)
  //(cam-outside-bsp        uint8                            :offset        152)
  //(cam-using-back         uint8                            :offset-assert 153)
  //(cam-box-idx            uint16                           :offset-assert 154)
  //(ambients               symbol                           :offset-assert 156)
  //(subdivide-close        float                            :offset-assert 160)
  //(subdivide-far          float                            :offset-assert 160)
  //(race-meshes            (array entity-race-mesh)         :offset-assert 168)
  //(actor-birth-order      (pointer uint32)                 :offset-assert 172)
  gen.link_word_to_byte(172 / 4, generate_u32_array(actor_birth_order, gen));
  //(light-hash             light-hash                       :offset-assert 176)
  //(nav-meshes             (array entity-nav-mesh)          :offset-assert 180)
  //(actor-groups           (array actor-group)              :offset-assert 184)
  gen.link_word_to_byte(184 / 4, generate_actor_group_array(gen, actor_groups));
  //(region-trees           (array drawable-tree-region-prim) :offset-assert 188)
  gen.link_word_to_byte(188 / 4,
                        generate_drawable_tree_region_prim_array(gen, region_array, region_trees));
  //(region-array           region-array                     :offset-assert 192)
  gen.link_word_to_byte(192 / 4, region_array.slot);
  //(collide-hash           collide-hash                     :offset-assert 196)
  gen.link_word_to_byte(196 / 4, add_to_object_file(collide_hash, gen));
  //(wind-array             uint32                           :offset        200)
  //(wind-array-length      int32                            :offset        204)
  //(city-level-info        city-level-info                  :offset        208)
  //(vis-spheres            vector-array                     :offset        216)
  //(vis-spheres-length     uint32                           :offset        248)
  //(region-tree            drawable-tree-region-prim        :offset        252)
  //(tfrag-masks            texture-masks-array              :offset-assert 256)
  //(tfrag-closest          (pointer float)                  :offset-assert 260)
  //(tfrag-mask-count       uint32                           :offset        260)
  //(shrub-masks            texture-masks-array              :offset-assert 264)
  //(shrub-closest          (pointer float)                  :offset-assert 268)
  //(shrub-mask-count       uint32                           :offset        268)
  //(alpha-masks            texture-masks-array              :offset-assert 272)
  //(alpha-closest          (pointer float)                  :offset-assert 276)
  //(alpha-mask-count       uint32                           :offset        276)
  //(water-masks            texture-masks-array              :offset-assert 280)
  //(water-closest          (pointer float)                  :offset-assert 284)
  //(water-mask-count       uint32                           :offset        284)
  //(bsp-scale              vector :inline                   :offset-assert 288)
  //(bsp-offset             vector :inline                   :offset-assert 304)
  //(hfrag-drawable         drawable                         :offset        320)
  //(end                    uint8                            :offset        399)

  return gen.generate_v2();
}
}  // namespace jak3