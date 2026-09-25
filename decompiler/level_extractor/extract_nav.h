#pragma once

#include <string>
#include <utility>
#include <vector>

#include "decompiler/ObjectFile/LinkedObjectFile.h"

namespace level_tools {

/*!
 * A relocatable copy of the GOAL data reachable from some pointers of a linked object file: every
 * object (label to label) the roots lead to, in their original order and 16-byte alignment, as
 * words, with how each word links (a pointer into the copy, a type, a symbol, the empty list).
 * Written as json for the level builder (goalc/build_level), which re-emits it in a bsp.
 */
struct DataGraphCopy {
  std::vector<u32> words;
  std::vector<std::pair<int, int>> pointers;         // word index -> byte offset in the copy
  std::vector<std::pair<int, std::string>> types;    // word index -> type name
  std::vector<std::pair<int, std::string>> symbols;  // word index -> symbol name
  std::vector<int> empty_lists;                      // word index
  std::vector<std::pair<std::string, int>> roots;    // name -> byte offset in the copy
};

/*!
 * Copy the data reachable from roots: (name, byte offset of a pointer word in segment seg).
 */
DataGraphCopy copy_data_graph(const decompiler::LinkedObjectFile& file,
                              int seg,
                              const std::vector<std::pair<std::string, int>>& roots);

std::string data_graph_copy_to_json(const DataGraphCopy& copy);

}  // namespace level_tools
