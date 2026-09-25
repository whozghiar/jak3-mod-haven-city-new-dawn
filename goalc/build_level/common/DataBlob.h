#pragma once

#include <map>
#include <string>
#include <utility>
#include <vector>

#include "common/common_types.h"

#include "goalc/data_compiler/DataObjectGenerator.h"

/*!
 * Relocatable GOAL data made outside the builder (the decompiler's data graph copies, see
 * decompiler/level_extractor/extract_nav.h, or a generator merging some): words, and how each word
 * links: a pointer into the blob, a type, a symbol, the empty list. Roots name byte offsets in it.
 */
struct DataBlob {
  std::vector<u32> words;
  std::vector<std::pair<int, int>> pointers;         // word index -> byte offset in the blob
  std::vector<std::pair<int, std::string>> types;    // word index -> type name
  std::vector<std::pair<int, std::string>> symbols;  // word index -> symbol name
  std::vector<int> empty_lists;                      // word index
  std::map<std::string, int> roots;                  // name -> byte offset in the blob

  static DataBlob from_json_file(const std::string& path);

  /*!
   * Add the blob to the object, 16-byte aligned as it was made. Returns its byte offset there:
   * add a root's offset to link to it.
   */
  int add_to(DataObjectGenerator& gen) const;
};
