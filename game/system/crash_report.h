#pragma once

/*!
 * @file crash_report.h
 * When the runtime crashes (Windows), write where it crashed to stderr, log/<game>-crash.txt and
 * the log before the process dies: the native module and offset, or for GOAL code the function
 * (its symbol, method or state handler), the process running it and its state. See
 * crash_report.cpp.
 */

#include <string>

namespace crash_report {
void install(const std::string& game_name);
}  // namespace crash_report
