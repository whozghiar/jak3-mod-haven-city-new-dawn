/*!
 * @file crash_report.cpp
 * Crash report, Windows only: when the runtime crashes, write where to stderr, log/<game>-crash.txt
 * and the log. The exception is not handled: the process still ends like before.
 *
 * GOAL code runs on stacks in GOAL memory, outside its thread's native stack: Windows stops
 * looking for a handler there and ends the process without calling the unhandled exception filter
 * (and without an error report). So a vectored handler, called before that search, catches the
 * fatal exceptions of GOAL code and of gk itself (nothing in them handles one); the unhandled
 * exception filter catches the others. Both copy the exception to a report thread and wait for
 * it: the report needs more stack than a GOAL stack may have left.
 *
 * The runtime has no debug info for GOAL code, so the names come from the symbol table (Jak 3's
 * layout): a function is found by its type tag (the 4 bytes before its first instruction), then
 * named by the symbol holding it, the type whose method it is, or the state whose handler it is. A
 * lambda has no name: it is given the closest named function before it, in the same object file.
 * The stack is then scanned for return addresses, a heuristic (some entries can be stale).
 */

#include "crash_report.h"

#ifdef _WIN32

#define NOMINMAX
#define WIN32_LEAN_AND_MEAN
#include <Windows.h>
#include <algorithm>
#include <atomic>
#include <cstring>
#include <map>
#include <string>
#include <utility>

#include "common/common_types.h"
#include "common/goal_constants.h"
#include "common/listener_common.h"
#include "common/log/log.h"
#include "common/symbols.h"
#include "common/util/FileUtil.h"
#include "common/util/unicode_util.h"

#include "game/kernel/common/kprint.h"
#include "game/kernel/common/kscheme.h"
#include "game/kernel/jak3/kscheme.h"
#include "game/runtime.h"

#include "fmt/format.h"

namespace crash_report {
namespace {

/*!
 * Is this native address in GOAL memory (the protected low pages included)?
 */
bool in_goal_memory(u64 native) {
  const u64 base = (u64)g_ee_main_mem;
  return g_ee_main_mem && native >= base && native < base + EE_MAIN_MEM_SIZE;
}

/*!
 * Can this range of GOAL memory be read? (The low pages are protected.)
 */
bool goal_readable(u64 addr, u64 size) {
  return g_ee_main_mem && addr >= (u64)EE_MAIN_MEM_LOW_PROTECT &&
         addr + size <= (u64)EE_MAIN_MEM_SIZE;
}

u32 read_u32(u64 addr) {
  u32 value = 0;
  if (goal_readable(addr, 4)) {
    memcpy(&value, g_ee_main_mem + addr, 4);
  }
  return value;
}

/*!
 * The GOAL address of a native address in readable GOAL memory, or 0.
 */
u64 goal_address(u64 native) {
  const u64 base = (u64)g_ee_main_mem;
  if (in_goal_memory(native) && native >= base + EE_MAIN_MEM_LOW_PROTECT) {
    return native - base;
  }
  return 0;
}

/*!
 * "module+offset" for a native address in a loaded module, or an empty string.
 */
std::string module_address(u64 native) {
  HMODULE module = nullptr;
  if (!GetModuleHandleExA(
          GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
          (LPCSTR)native, &module) ||
      !module) {
    return "";
  }
  char path[MAX_PATH] = {0};
  GetModuleFileNameA(module, path, MAX_PATH);
  const char* name = strrchr(path, '\\');
  return fmt::format("{}+0x{:x}", name ? name + 1 : path, native - (u64)module);
}

/*!
 * Names of Jak 3's GOAL functions, from its symbol table.
 */
class Jak3Names {
 public:
  bool build() {
    if (!s7.offset || !SymbolTable2.offset || !LastSymbol.offset || !jak3::SymbolString.offset) {
      return false;
    }
    m_function_type = symbol_value(s7.offset + jak3_symbols::FIX_SYM_FUNCTION_TYPE);
    m_type_type = symbol_value(s7.offset + jak3_symbols::FIX_SYM_TYPE_TYPE);
    m_string_type = symbol_value(s7.offset + jak3_symbols::FIX_SYM_STRING_TYPE);
    for (u32 sym = SymbolTable2.offset; sym < LastSymbol.offset; sym += 4) {
      const u32 value = symbol_value(sym);
      if (value && type_of(value) == m_type_type) {
        const std::string name = symbol_name(sym);
        if (name == "state") {
          m_state_type = value;
        } else if (name == "level") {
          m_level_type = value;
        }
      }
    }
    for (u32 sym = SymbolTable2.offset; sym < LastSymbol.offset; sym += 4) {
      const u32 value = symbol_value(sym);
      const u32 type = type_of(value);
      if (!type) {
        continue;
      }
      if (type == m_function_type) {
        add(value, symbol_name(sym));
      } else if (type == m_type_type) {
        add_methods(value, symbol_name(sym));
      } else if (m_state_type && type == m_state_type) {
        add_state(value, "(state ");
      }
    }
    return m_function_type != 0;
  }

  /*!
   * The function containing this GOAL address.
   */
  std::string function_at(u32 addr) const {
    // a function's first instruction is right after its type tag
    for (u32 start = addr & ~3u;
         start >= (u32)EE_MAIN_MEM_LOW_PROTECT + 4 && addr - start < (1u << 20); start -= 4) {
      if (read_u32(start - 4) != m_function_type) {
        continue;
      }
      const auto found = m_functions.find(start);
      if (found != m_functions.end()) {
        return fmt::format("{} +0x{:x}", found->second, addr - start);
      }
      // a lambda: the closest named function before it is in the same object file
      std::string before;
      auto below = m_functions.lower_bound(start);
      if (below != m_functions.begin()) {
        --below;
        before = fmt::format(", after {} (#x{:x})", below->second, below->first);
      }
      return fmt::format("anonymous function #x{:x} +0x{:x}{}", start, addr - start, before);
    }
    return "(no function found)";
  }

  /*!
   * The process in pp (the GOAL register r13): its name, type, state and level.
   */
  std::string process(u32 pp) const {
    const u32 type = type_of(pp);
    if (!goal_readable(pp, 0x80) || !type || type_of(type) != m_type_type) {
      return "(none)";
    }
    // a basic's fields are 4 bytes before their offset: name at 4, level at 60, state at 64
    const u32 state = read_u32(pp + 60);
    const u32 level = read_u32(pp + 56);
    return fmt::format(
        "{} (type {}), state {}, level {}", string_at(read_u32(pp)), type_name(type),
        m_state_type && type_of(state) == m_state_type ? symbol_name(read_u32(state)) : "#f",
        m_level_type && type_of(level) == m_level_type ? symbol_name(read_u32(level)) : "#f");
  }

  /*!
   * What a register holds, if it is a GOAL object: a symbol or a basic (its type). Else empty.
   */
  std::string object(u64 value) const {
    if (value >= SymbolTable2.offset && value < LastSymbol.offset && !((value - s7.offset) & 3)) {
      return "'" + symbol_name((u32)value);
    }
    if (value >= EE_MAIN_MEM_SIZE) {
      return "";
    }
    const u32 type = type_of((u32)value);
    return type && type_of(type) == m_type_type ? "a " + type_name(type) : "";
  }

  // a symbol's value is 1 byte before its address
  static u32 symbol_value(u32 sym) { return read_u32(sym - 1); }

  // a basic is at 4 mod 8, its type 4 bytes before it
  static u32 type_of(u32 obj) { return (obj & 7) == 4 ? read_u32(obj - 4) : 0; }

  static std::string symbol_name(u32 sym) {
    if (sym < SymbolTable2.offset || sym >= LastSymbol.offset || ((sym - s7.offset) & 3)) {
      return "?";
    }
    return raw_string(read_u32(jak3::SymbolString.offset + sym - s7.offset));
  }

  static std::string raw_string(u32 str) {
    const u32 length = read_u32(str);
    if (!length || length > 256 || !goal_readable(str + 4, length)) {
      return "?";
    }
    const char* data = (const char*)g_ee_main_mem + str + 4;
    return std::string(data, strnlen(data, length));
  }

 private:
  std::string string_at(u32 str) const {
    return type_of(str) == m_string_type ? raw_string(str) : "?";
  }

  static std::string type_name(u32 type) { return symbol_name(read_u32(type)); }

  static u32 method_count(u32 type) { return read_u32(type + 12) >> 16; }

  void add(u32 function, const std::string& name) {
    if (function && type_of(function) == m_function_type) {
      m_functions.emplace(function, name);
    }
  }

  void add_methods(u32 type, const std::string& name) {
    const u32 parent = read_u32(type + 4);
    const u32 parent_count = type_of(parent) == m_type_type ? method_count(parent) : 0;
    const u32 count = std::min(method_count(type), 256u);
    for (u32 i = 0; i < count; i++) {
      const u32 method = read_u32(type + 16 + 4 * i);
      if (i < parent_count && read_u32(parent + 16 + 4 * i) == method) {
        continue;  // inherited: named with the type that defines it
      }
      if (type_of(method) == m_function_type) {
        add(method, fmt::format("(method {} {})", i, name));
      } else if (m_state_type && type_of(method) == m_state_type) {
        add_state(method, fmt::format("({} ", name));  // a virtual state
      }
    }
  }

  void add_state(u32 state, const std::string& prefix) {
    // name at 4, exit at 12, code at 20, trans at 24, post at 28, enter at 32, event at 36
    const std::string name = prefix + symbol_name(read_u32(state)) + ")";
    add(read_u32(state + 16), name + " :code");
    add(read_u32(state + 20), name + " :trans");
    add(read_u32(state + 24), name + " :post");
    add(read_u32(state + 28), name + " :enter");
    add(read_u32(state + 8), name + " :exit");
    add(read_u32(state + 32), name + " :event");
  }

  u32 m_function_type = 0;
  u32 m_type_type = 0;
  u32 m_string_type = 0;
  u32 m_state_type = 0;
  u32 m_level_type = 0;
  std::map<u32, std::string> m_functions;
};

std::string describe(u64 native, const Jak3Names* names) {
  if (const u64 goal = goal_address(native)) {
    return names ? fmt::format("GOAL #x{:x} in {}", goal, names->function_at((u32)goal))
                 : fmt::format("GOAL #x{:x}", goal);
  }
  if (in_goal_memory(native)) {
    return fmt::format("GOAL #x{:x}, protected low memory: a call through a null function pointer",
                       native - (u64)g_ee_main_mem);
  }
  const std::string module = module_address(native);
  return module.empty() ? fmt::format("0x{:x} (no module)", native) : module;
}

const char* exception_name(DWORD code) {
  switch (code) {
    case EXCEPTION_ACCESS_VIOLATION:
      return "access violation";
    case EXCEPTION_ILLEGAL_INSTRUCTION:
      return "illegal instruction";
    case EXCEPTION_PRIV_INSTRUCTION:
      return "privileged instruction";
    case EXCEPTION_INT_DIVIDE_BY_ZERO:
      return "integer divide by zero";
    case EXCEPTION_INT_OVERFLOW:
      return "integer overflow";
    case EXCEPTION_STACK_OVERFLOW:
      return "stack overflow";
    case EXCEPTION_BREAKPOINT:
      return "breakpoint";
    case EXCEPTION_IN_PAGE_ERROR:
      return "in-page error";
    default:
      return "exception";
  }
}

bool is_fatal(DWORD code) {
  switch (code) {
    case EXCEPTION_ACCESS_VIOLATION:
    case EXCEPTION_ILLEGAL_INSTRUCTION:
    case EXCEPTION_PRIV_INSTRUCTION:
    case EXCEPTION_INT_DIVIDE_BY_ZERO:
    case EXCEPTION_INT_OVERFLOW:
    case EXCEPTION_STACK_OVERFLOW:
    case EXCEPTION_BREAKPOINT:
    case EXCEPTION_IN_PAGE_ERROR:
      return true;
    default:
      return false;
  }
}

/*!
 * What the thread that crashed leaves for the report thread.
 */
struct Capture {
  EXCEPTION_RECORD record;
  CONTEXT context;
  DWORD thread_id;
  u64 stack_limit;  // its native stack
  u64 stack_base;
};

Capture g_capture;
std::atomic<bool> g_crashed{false};
HANDLE g_request = nullptr;
HANDLE g_done = nullptr;
std::wstring g_crash_path;
u64 g_gk_begin = 0;  // gk.exe in memory
u64 g_gk_end = 0;

std::string thread_name(DWORD id) {
  std::string name;
  if (HANDLE thread = OpenThread(THREAD_QUERY_LIMITED_INFORMATION, false, id)) {
    PWSTR wide = nullptr;
    if (SUCCEEDED(GetThreadDescription(thread, &wide)) && wide) {
      for (const wchar_t* c = wide; *c; c++) {
        name.push_back(*c < 128 ? (char)*c : '?');
      }
      LocalFree(wide);
    }
    CloseHandle(thread);
  }
  return name.empty() ? fmt::format("#{}", id) : fmt::format("{} (#{})", name, id);
}

/*!
 * The return addresses found on the thread's stack, newest first. GOAL code runs on stacks in GOAL
 * memory.
 */
void scan_stack(const Capture& capture, const Jak3Names* names, std::string& out) {
  const u64 rsp = capture.context.Rsp;
  u64 top = 0;
  if (goal_address(rsp)) {
    top = (u64)g_ee_main_mem + EE_MAIN_MEM_SIZE;
  } else if (rsp >= capture.stack_limit && rsp < capture.stack_base) {
    top = capture.stack_base;
  } else {
    out += "  (stack not readable)\n";
    return;
  }
  top = std::min(top, rsp + 0x8000);
  std::string last;
  int count = 0;
  for (u64 slot = rsp & ~7ull; slot + 8 <= top && count < 24; slot += 8) {
    u64 value = 0;
    memcpy(&value, (const void*)slot, 8);
    std::string where;
    if (goal_address(value)) {
      where = describe(value, names);
    } else {
      where = module_address(value);
    }
    if (where.empty() || where == last) {
      continue;
    }
    last = where;
    count++;
    out += fmt::format("  [rsp+0x{:x}] {}\n", slot - rsp, where);
  }
}

/*!
 * What GOAL printed with (format #t ...) since the last frame: printed at the end of a frame, so
 * a crash would lose it.
 */
std::string pending_goal_output() {
  if (!PrintBufArea.offset) {
    return "";
  }
  const u64 start = PrintBufArea.offset + sizeof(ListenerMessageHeader);
  if (!goal_readable(start, 1)) {
    return "";
  }
  const char* text = (const char*)g_ee_main_mem + start;
  const u64 room = std::min<u64>(PrintBufSize, (u64)EE_MAIN_MEM_SIZE - start);
  const std::string output(text, strnlen(text, room));
  // the end is what matters
  return output.size() > 4000 ? "..." + output.substr(output.size() - 4000) : output;
}

std::string build_report(const Capture& capture) {
  const EXCEPTION_RECORD& record = capture.record;
  const CONTEXT& ctx = capture.context;

  Jak3Names names;
  const Jak3Names* goal_names =
      g_game_version == GameVersion::Jak3 && names.build() ? &names : nullptr;

  std::string report = "======== crash report ========\n";
  report += fmt::format("{} (0x{:08x}) in thread {}\n", exception_name(record.ExceptionCode),
                        (u32)record.ExceptionCode, thread_name(capture.thread_id));
  if (record.ExceptionCode == EXCEPTION_ACCESS_VIOLATION && record.NumberParameters >= 2) {
    const u64 target = record.ExceptionInformation[1];
    report += fmt::format("{} 0x{:x}",
                          record.ExceptionInformation[0] == 0   ? "reading"
                          : record.ExceptionInformation[0] == 1 ? "writing"
                                                                : "executing",
                          target);
    if (in_goal_memory(target)) {
      report += fmt::format(" (GOAL #x{:x})", target - (u64)g_ee_main_mem);
    }
    report += "\n";
  }
  report += fmt::format("at {}\n", describe(ctx.Rip, goal_names));
  if (goal_names) {
    report += fmt::format("process (r13): {}\n", goal_names->process((u32)ctx.R13));
  }
  report += fmt::format("rax {:016x} rbx {:016x} rcx {:016x} rdx {:016x}\n", ctx.Rax, ctx.Rbx,
                        ctx.Rcx, ctx.Rdx);
  report += fmt::format("rsi {:016x} rdi {:016x} rbp {:016x} rsp {:016x}\n", ctx.Rsi, ctx.Rdi,
                        ctx.Rbp, ctx.Rsp);
  report += fmt::format("r8  {:016x} r9  {:016x} r10 {:016x} r11 {:016x}\n", ctx.R8, ctx.R9,
                        ctx.R10, ctx.R11);
  report += fmt::format("r12 {:016x} r13 {:016x} r14 {:016x} r15 {:016x}\n", ctx.R12, ctx.R13,
                        ctx.R14, ctx.R15);
  if (goal_names) {
    // GOAL arguments are rdi rsi rdx rcx r8 r9 r10 r11, the result rax
    const std::pair<const char*, u64> registers[] = {
        {"rax", ctx.Rax}, {"rbx", ctx.Rbx}, {"rcx", ctx.Rcx}, {"rdx", ctx.Rdx},
        {"rsi", ctx.Rsi}, {"rdi", ctx.Rdi}, {"rbp", ctx.Rbp}, {"r8", ctx.R8},
        {"r9", ctx.R9},   {"r10", ctx.R10}, {"r11", ctx.R11}, {"r12", ctx.R12}};
    std::string objects;
    for (const auto& [name, value] : registers) {
      const std::string what = goal_names->object(value);
      if (!what.empty()) {
        objects += fmt::format(" {}: {},", name, what);
      }
    }
    if (!objects.empty()) {
      objects.pop_back();
      report += fmt::format("GOAL objects:{}\n", objects);
    }
  }
  report += "stack, return addresses (newest first):\n";
  scan_stack(capture, goal_names, report);
  const std::string output = pending_goal_output();
  if (!output.empty()) {
    report += "GOAL output of this frame, not printed yet:\n" + output;
    if (report.back() != '\n') {
      report += "\n";
    }
  }
  report += "==============================\n";
  return report;
}

void write_raw(HANDLE file, const std::string& text) {
  DWORD written = 0;
  WriteFile(file, text.data(), (DWORD)text.size(), &written, nullptr);
}

void write_report(const Capture& capture) {
  const std::string report = build_report(capture);
  // stderr and a file of its own first: no lock the crashed thread could hold
  write_raw(GetStdHandle(STD_ERROR_HANDLE), "\n" + report);
  if (!g_crash_path.empty()) {
    HANDLE file = CreateFileW(g_crash_path.c_str(), GENERIC_WRITE, FILE_SHARE_READ, nullptr,
                              CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file != INVALID_HANDLE_VALUE) {
      write_raw(file, report);
      CloseHandle(file);
    }
  }
  lg::error("\n{}", report);
}

DWORD WINAPI report_thread(LPVOID) {
  WaitForSingleObject(g_request, INFINITE);
  write_report(g_capture);
  SetEvent(g_done);
  return 0;
}

/*!
 * On the thread that crashed: copy the exception and let the report thread write the report (a
 * GOAL stack may have little room left).
 */
void capture(const EXCEPTION_POINTERS* info) {
  if (g_crashed.exchange(true)) {
    return;
  }
  memcpy(&g_capture.record, info->ExceptionRecord, sizeof(EXCEPTION_RECORD));
  memcpy(&g_capture.context, info->ContextRecord, sizeof(CONTEXT));
  g_capture.thread_id = GetCurrentThreadId();
  const NT_TIB* tib = (const NT_TIB*)NtCurrentTeb();
  g_capture.stack_limit = (u64)tib->StackLimit;
  g_capture.stack_base = (u64)tib->StackBase;
  if (g_request && g_done) {
    SetEvent(g_request);
    WaitForSingleObject(g_done, 20000);
  } else {
    write_report(g_capture);
  }
}

LONG CALLBACK vectored_handler(EXCEPTION_POINTERS* info) {
  const u64 rip = info->ContextRecord->Rip;
  if (is_fatal(info->ExceptionRecord->ExceptionCode) &&
      (in_goal_memory(rip) || (rip >= g_gk_begin && rip < g_gk_end))) {
    capture(info);
  }
  return EXCEPTION_CONTINUE_SEARCH;
}

LONG WINAPI unhandled_filter(EXCEPTION_POINTERS* info) {
  capture(info);
  return EXCEPTION_CONTINUE_SEARCH;
}

}  // namespace

void install(const std::string& game_name) {
  g_crash_path =
      utf8_string_to_wide_string(file_util::get_file_path({"log", game_name + "-crash.txt"}));
  const u8* gk = (const u8*)GetModuleHandleA(nullptr);
  const auto* dos = (const IMAGE_DOS_HEADER*)gk;
  const auto* nt = (const IMAGE_NT_HEADERS*)(gk + dos->e_lfanew);
  g_gk_begin = (u64)gk;
  g_gk_end = g_gk_begin + nt->OptionalHeader.SizeOfImage;
  g_request = CreateEventA(nullptr, true, false, nullptr);
  g_done = CreateEventA(nullptr, true, false, nullptr);
  HANDLE thread = g_request && g_done
                      ? CreateThread(nullptr, 1 << 20, report_thread, nullptr, 0, nullptr)
                      : nullptr;
  if (thread) {
    CloseHandle(thread);  // it keeps running
  } else {
    g_request = nullptr;  // the thread that crashed writes the report itself
    g_done = nullptr;
  }
  AddVectoredExceptionHandler(1, vectored_handler);
  SetUnhandledExceptionFilter(unhandled_filter);
}

}  // namespace crash_report

#else

namespace crash_report {
void install(const std::string&) {}
}  // namespace crash_report

#endif
