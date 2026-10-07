"""Jak 3 as a target game: its level heap, and the GOAL text of its level-load-infos and continue
points."""

NAME = "jak3"
TITLE = "Jak 3"
ISO = "iso_data/jak3"
FR3 = "out/jak3/fr3"
METER = 4096.0

# Jak 3's level heap is 18 chunks. A level of each memory mode takes one of these chunk sets (the
# plain case of level-group::alloc-levels!, goal_src/jak3/engine/level/level.gc, no micro or tiny
# level loaded), so levels fit together when they can take chunk sets that don't overlap. Jak 2's
# load-buffer-mode has the same four names (small-edge when a level has none).
CHUNKS = {
    "large": [0xFFF, 0x3FFC0],
    "medium": [0x1FF, 0x3FE00],
    "small-center": [0xFC0],
    "small-edge": [0x3F, 0x3F000],
}
CHUNK_COUNT = {mode: bin(masks[0]).count("1") for mode, masks in CHUNKS.items()}
# the memory modes, smallest first
MEMORY_ORDER = ["small-edge", "small-center", "medium", "large"]


def fits(modes):
    """Can levels of these memory modes be loaded together?"""
    def place(i, used):
        return i == len(modes) or any(not mask & used and place(i + 1, used | mask)
                                      for mask in CHUNKS[modes[i]])
    return place(0, 0)


def int16(x):
    return max(-32768, min(32767, int(round(x * 32767))))


def continue_point(cont_name, level, trans, camera_trans, quat, camera_rot, flags, wants,
                   want_sound="#f #f #f", indent=6):
    """A continue-point (positions in game units, rotations as floats)."""
    pad = " " * indent
    t, c, q = trans, camera_trans, quat
    rot = " ".join(str(int16(x)) for x in camera_rot)
    want_lines = "\n".join(
        f"{pad}    (new 'static 'level-buffer-state-small :name '{name} :display? {disp})"
        for name, disp in wants
    )
    flags_line = f"{pad}  :flags (continue-flags {' '.join(flags)})\n" if flags else ""
    return f"""{pad}(new 'static 'continue-point
{pad}  :name "{cont_name}"
{pad}  :level '{level}
{pad}  :trans (static-vectorm {t[0] / METER:.4f} {t[1] / METER:.4f} {t[2] / METER:.4f})
{pad}  :camera-trans (static-vectorm {c[0] / METER:.4f} {c[1] / METER:.4f} {c[2] / METER:.4f})
{pad}  :quat (new 'static 'vector4h :data (new 'static 'array int16 4 {int16(q[0])} {int16(q[1])} {int16(q[2])} {int16(q[3])}))
{pad}  :camera-rot (new 'static 'array int16 9 {rot})
{flags_line}{pad}  :on-goto #f
{pad}  :vis-nick '{level}
{pad}  :vehicle-type #x1b
{pad}  :want-count {len(wants)}
{pad}  :want (new 'static 'inline-array level-buffer-state-small {len(wants)}
{want_lines}
{pad}    )
{pad}  :want-sound (new 'static 'array symbol 3 {want_sound})
{pad}  )"""


def level_load_info(name, nick, index, memory_mode, flags, mood, continues, callbacks, ocean,
                    comment, draw_priority, outdoor, part_engine_max=0, music="#f",
                    extra_sound_bank="#f", city_map_bits=0):
    """A level-load-info, and its registration in *level-load-list*. city_map_bits: the squares of
    the city's 5x7 minimap grid (bit 5 * row + column) whose map the level holds."""
    flags_line = f"    :level-flags (level-flags {flags})\n" if flags else ""
    bits = " ".join(f"cmb{i}" for i in range(34) if city_map_bits >> i & 1)
    map_line = f"    :city-map-bits (city-map-bits {bits})\n" if bits else ""
    if outdoor:
        # the weather of an outdoor level: clouds and fog anywhere in 0..1, rain when both are high
        weather = ("    :max-rain 1.0\n"
                   "    :mood-range (new 'static 'mood-range :max-cloud 1.0 :max-fog 1.0)\n")
    else:
        weather = "    :max-rain 0.0\n    :mood-range (new 'static 'mood-range)\n"
    ocean_value = f"'{ocean}" if ocean else "#f"
    callback_list = (
        "'(" + " ".join(f"({slot} . {fn})" for slot, fn in callbacks) + ")" if callbacks else "'()"
    )
    return f"""{comment}
(define {name}
  (new 'static 'level-load-info
    :name '{name}
    :visname '{name}-vis
    :nickname '{nick}
    :dbname '{name}
    :taskname 'default
    :index #x{index:x}
    :master-level #f
{flags_line}    :packages '()
    :run-packages '("common")
    :memory-mode (level-memory-mode {memory_mode})
    :music-bank {music}
    :extra-sound-bank {extra_sound_bank}
    :mood-func '{mood}
    :special-mood #f
    :ocean {ocean_value}
    :ocean-alpha 1.0
    :priority 100
    :draw-priority {draw_priority}
{map_line}    :part-engine-max {part_engine_max}
    :base-task-mask (task-mask task0)
    :bigmap-id (bigmap-id none)
    :continues '(
{chr(10).join(continues)}
      )
    :callback-list {callback_list}
    :borrow #f
    :bottom-height (meters -100)
    :fog-height (meters 80)
{weather}    :fog-mult 1.0
    )
  )

(cons! *level-load-list* '{name})
"""
