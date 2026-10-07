"""The source game's sound in the port (the manifest's "sound" block): its sound banks and music.

The levels keep the source game's sound: their scripts' sound banks (want-sound) and looped
ambiences (sound-play-loop), their continues' sound banks, their music (the level-load-infos'
:music-bank). The files keep the source game's content, under new names: both games have files of
the same name (Jak 2's FOREST1.SBK isn't Jak 3's), so each gets the manifest's "prefix", shortened
to the disc's 8 characters (Jak 2's CTYWIDE1.SBK: J2CTYWI1.SBK, the bank 'j2ctywi1). The build
copies the files the levels use from the source game's extracted disc (iso_data/<game>) to the
target game's (out/<game>/iso), when they are there (the absolute path of the player's
disc when the port runs with --iso, at a mod's install): without them the levels are silent.

Voice lines (the source game's VAG files: speeches, citizens' lines) are packed by goalc's
pack-vags tool into a directory and wads of the target game's format (VAGDIRM.AYB,
VAGWADM.<language>), which the Jak 3 overlord adds to its own (game/overlord/jak3/iso.cpp). They
get the "voice_prefix" (a name of the source game's could be one the target game's code plays).

Block keys: "prefix" (the new names' start), "extra_banks" (source bank -> target game banks loaded
with it, while a hub is loaded: Jak 3's traffic sounds with Jak 2's city banks), "music" (source
musics the mod's code plays itself, copied like the levels'), "voice_prefix",
"voices" (GOAL variable -> its lines: the level-info file defines each as an array of the lines'
new names, for the mod's code to play).
"""

import re

# the disc's file names: 8 characters and an extension
NAME_LENGTH = 8
# the languages of Jak 2's voice wads (VAGWAD.<language>)
VOICE_LANGUAGES = ["ENG", "FRE", "GER", "ITA", "JAP", "KOR", "SPA"]


def renamed(prefix, name):
    """A source game file's name in the target game: prefix + name, its letters cut to fit 8
    characters (its number kept)."""
    name = name.lower()
    if len(prefix + name) <= NAME_LENGTH:
        return prefix + name
    stem, number = re.fullmatch(r"(.*?)(\d*)", name).groups()
    return prefix + stem[:NAME_LENGTH - len(prefix) - len(number)] + number


class Sound:
    """The source game's sound files the levels use, by their new names (filled while the steps
    translate the scripts and write the level-load-infos)."""

    def __init__(self, port):
        cfg = port["sound"]
        self.prefix = cfg["prefix"]
        self.extra_banks = cfg.get("extra_banks", {})
        self.voice_prefix = cfg.get("voice_prefix", "")
        self.voices = cfg.get("voices", {})
        self.build_file = port["build"]["file"]
        self.source = port.source.NAME
        # its extracted disc: iso_data/<game>, or the absolute path of a launcher install (--iso)
        self.iso = port.source.ISO
        self.source_title = port.source.TITLE
        self.target_title = port.target.TITLE
        self.banks = {}  # new name -> source name
        self.music = {}
        # musics the mod's code plays besides the levels' (a mini-game's)
        for name in cfg.get("music", []):
            self.music_bank(name)

    def _use(self, used, name):
        new = renamed(self.prefix, name)
        assert used.setdefault(new, name) == name, f"{name} and {used[new]} are both {new}"
        return new

    def bank(self, name):
        """The new name of a source sound bank (a want-sound's), noted for the build."""
        return self._use(self.banks, name)

    def music_bank(self, name):
        """The new name of a source music, noted for the build."""
        return self._use(self.music, name)

    def extra_sound_bank(self):
        """The :extra-sound-bank of a hub: each source bank of "extra_banks" and the target game
        banks loaded with it."""
        pairs = [f"({self.bank(src)} {self.bank(src)} {' '.join(extra)})"
                 for src, extra in self.extra_banks.items()]
        return "'(" + " ".join(pairs) + ")" if pairs else "#f"

    def voice(self, name):
        """A source voice line's new name."""
        new = self.voice_prefix + name
        assert len(new) <= NAME_LENGTH, f"{new}: longer than {NAME_LENGTH} characters"
        return new

    def voice_defines(self):
        """GOAL text: the "voices" variables, each an array of its lines' new names."""
        out = []
        for var, lines in self.voices.items():
            out += [f"(define {var} (new 'static 'boxed-array :type string",
                    *[f'  "{self.voice(x)}"' for x in lines], "  ))", ""]
        return out

    def build_lines(self):
        """The goalc build steps copying the files, each only when the source game's disc has it
        (file-exists?)."""
        lines = ["", f";; {self.source_title}'s sound banks and music the levels use, copied from its "
                 "extracted disc when it is", ";; there (renamed: scripts/level_port/steps/sound.py)"]
        for used, ext in ((self.banks, "SBK"), (self.music, "MUS")):
            for new, name in sorted(used.items()):
                src = f"{self.iso}/{ext}/{name.upper()}.{ext}"
                out = f"$OUT/iso/{new.upper()}.{ext}"
                # in the "iso" group (game.gp), with the target game's own sound banks
                lines += [f'(when (file-exists? "{src}")',
                          f'  (defstep :in "{src}" :tool \'copy :out \'("{out}"))',
                          f'  (set! *all-sbk* (cons "{out}" *all-sbk*)))']
        lines += self.voice_build_lines()
        return lines

    def voice_build_lines(self):
        """The pack-vags step of the voice lines (goalc/make/Tools.cpp), when the source game's
        disc has its VAG files. This build file is its third input: it runs again when the file
        changes (its line list)."""
        lines = list(dict.fromkeys(x for v in self.voices.values() for x in v))
        if not lines:
            return []
        src = f"{self.iso}/VAG/VAGDIR.AYB"
        outs = ["$OUT/iso/VAGDIRM.AYB"] + [f"$OUT/iso/VAGWADM.{lang}" for lang in VOICE_LANGUAGES]
        pairs = [f"({x} {self.voice(x)})" for x in lines]
        arg = ["    " + " ".join(pairs[i:i + 6]) for i in range(0, len(pairs), 6)]
        return ["", f";; {self.source_title}'s voice lines, packed for the {self.target_title} overlord "
                "(VAGDIRM.AYB, VAGWADM.<language>)",
                f'(when (file-exists? "{src}")',
                f'  (defstep :in \'("{src}" "$ISO/VAG/VAGDIR.AYB" "{self.build_file}")',
                "    :tool 'pack-vags",
                "    :arg '(", *arg, "      )",
                "    :out '(" + " ".join(f'"{o}"' for o in outs) + "))",
                *[f'  (set! *all-vag* (cons "{o}" *all-vag*))' for o in outs[:-1]],
                f'  (set! *all-vag* (cons "{outs[-1]}" *all-vag*)))']


if __name__ == "__main__":
    assert renamed("j2", "ctywide1") == "j2ctywi1"
    assert renamed("j2", "hiphog1") == "j2hipho1"
    assert renamed("j2", "city1") == "j2city1"
    assert renamed("j2", "danger10") == "j2dang10"
    assert renamed("j2", "mountain") == "j2mounta"
    print("ok")
