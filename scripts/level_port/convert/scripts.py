"""Translates the scripts a game stores in its entities and regions for the port's levels.

Jak 2 and Jak 3 drive their level loading with small GOAL scripts stored in door, elevator and
region data (want-load, want-display, want-vis...), in the same script language. The scripts are
kept as they are, with these changes:
  - level names: each source level becomes the port's level holding it; a level that isn't ported
    is dropped from the lists (a door only leading there never opens),
  - story checks (task-closed? / task-open?) are evaluated here, for one fixed state of the story,
  - calls that mean nothing in the target game (the source game's sounds, dialogs, cutscenes,
    settings...) are removed. Fixed cameras are kept when the camera itself is ported.
What the target game keeps is the game pair's (convert/<source>_<target>.py: DROPPED_CALLS,
KEPT_SELF_EVENTS, KEPT_QUERIES, KEPT_OTHER_EVENTS).
"""

import re


class Sym(str):
    """A symbol."""


class Str(str):
    """A string literal."""


class Opaque(str):
    """Something the dump couldn't print (#<entity-actor ...>): the call using it is dropped."""


TRUE = Sym("#t")
FALSE = Sym("#f")
QUOTE = Sym("quote")


class _Drop:
    """A statement with no effect left."""

    def __repr__(self):
        return "DROP"


DROP = _Drop()

TOKEN = re.compile(r"""\s*(?:(\()|(\))|(')|("(?:[^"\\]|\\.)*")|(#<)|([^\s()'"]+))""")


def parse(text):
    """All the forms in text."""
    pos = 0
    forms = []

    def read():
        nonlocal pos
        m = TOKEN.match(text, pos)
        if not m:
            raise ValueError(f"can't read {text[pos:pos + 40]!r}")
        pos = m.end()
        lpar, rpar, quote, string, opaque, atom = m.groups()
        if lpar:
            items = []
            while True:
                m2 = TOKEN.match(text, pos)
                if m2 and m2.group(2):
                    pos = m2.end()
                    return items
                items.append(read())
        if rpar:
            raise ValueError("unexpected )")
        if quote:
            return [QUOTE, read()]
        if string:
            return Str(string[1:-1])
        if opaque:
            depth = 1
            start = pos - 2
            while depth:
                depth += {"<": 1, ">": -1}.get(text[pos], 0)
                pos += 1
            return Opaque(text[start:pos])
        return Sym(atom)

    while text[pos:].strip():
        forms.append(read())
    return forms


def dump(form):
    if isinstance(form, list):
        if len(form) == 2 and form[0] == QUOTE:
            return "'" + dump(form[1])
        return "(" + " ".join(dump(f) for f in form) + ")"
    if isinstance(form, Str):
        return '"' + form + '"'
    return str(form)


def is_quoted(form):
    return isinstance(form, list) and len(form) == 2 and form[0] == QUOTE


def truth(form):
    """True/False for a constant, None when only known at runtime."""
    if form == TRUE:
        return True
    if form == FALSE:
        return False
    if is_quoted(form) or isinstance(form, Str):
        return True
    return None


def with_hubs(levels, hubs):
    """A list of levels loaded together, with the hub of each level that has one (hubs: level ->
    its hub) added if missing and moved first: a hub holds code its levels' actors use, so it must
    load before them and unload after them (the loader unloads the last loaded level first)."""
    first = []
    for lev in levels:
        hub = hubs.get(lev)
        if hub and hub not in first:
            first.append(hub)
    return first + [lev for lev in levels if lev not in first]


def no_effect(form):
    """A statement that does nothing (a constant)."""
    return not isinstance(form, list) or is_quoted(form)


class Translator:
    """Translates the scripts of one entity or region of the source game.

    pair:        the game pair's tables (convert/<source>_<target>.py)
    level_map:   source level -> our level, for the levels that are ported
    all_levels:  every source level name (to recognize the ones that aren't ported)
    hubs:        our level -> its hub, loaded first with it (see with_hubs)
    owner:       our level holding the script (where Jak is when it runs)
    story:       function(task name) -> True when that task is closed in the chosen story state
    continues:   source continue name -> ours
    renames:     source entity name -> ours, for events sent to other entities by name
    drop_events: (event, first argument) pairs to remove, e.g. ("jump-to", "'top")
    cameras:     the names of the fixed cameras that are ported (camera-191...)
    source:      the source level holding the script
    sound:       the source game's sound banks (steps/sound.py), None when the levels are silent
    """

    def __init__(self, pair, level_map, all_levels, hubs, owner, story, continues, renames=None,
                 drop_events=(), cameras=(), source=None, sound=None):
        self.pair = pair
        self.level_map = level_map
        self.all_levels = set(all_levels) | set(level_map)
        self.hubs = hubs
        self.owner = owner
        self.source = source
        self.story = story
        self.continues = continues
        self.renames = renames or {}
        self.drop_events = set(drop_events)
        self.cameras = set(cameras)
        self.sound = sound
        # set while translating a door's on-notice (see strict_notice): a quoted level list naming a
        # level that isn't ported (but these ones, backdrops) then keeps the door shut
        self.strict_levels = None

    # levels ######################################################################################

    def level(self, form):
        """Our level for a (quoted) source level symbol, None if not ported."""
        if is_quoted(form):
            form = form[1]
        if form == FALSE:
            return None
        return self.level_map.get(str(form))

    def level_list(self, items):
        out = []
        for it in items:
            lev = self.level(it)
            if lev and lev not in out:
                out.append(lev)
        return out

    # translation #################################################################################

    def strict_notice(self, text, backdrops=()):
        """A door's on-notice (the levels it waits for before it opens), translated: None when the
        list the story state picks names a level that isn't ported (but a backdrop), since behind
        the door there would be nothing to walk on. Only the branch the story state reaches counts
        (a cond's other branches may name levels that aren't ported)."""
        self.strict_levels = set(backdrops)
        try:
            return self.script(text, value=True)
        finally:
            self.strict_levels = None

    def script(self, text, value=False):
        """The translated script, or None when nothing is left.
        value: the script's result is used (on-notice), else only what it does."""
        forms = parse(text)
        if len(forms) != 1:
            raise ValueError(f"expected one form in {text!r}")
        out = self.tr(forms[0], value)
        if out is DROP:
            return None
        if value and out == FALSE:
            return None
        if not value and no_effect(out):
            return None
        return dump(out)

    def body(self, forms, value):
        """A begin-like sequence: drops the statements without effect, and ends with the value of
        the last form when the result is used."""
        out = []
        for i, f in enumerate(forms):
            last = i == len(forms) - 1
            t = self.tr(f, value and last)
            if value and last:
                out.append(FALSE if t is DROP else t)
            elif t is not DROP and not no_effect(t) and dump(t) not in [dump(o) for o in out]:
                # two source levels shown or hidden in a row may now be the same level
                out.append(t)
        return out

    def seq(self, forms, value):
        out = self.body(forms, value)
        if not out:
            return FALSE if value else DROP
        if len(out) == 1:
            return out[0]
        return [Sym("begin")] + out

    def tr(self, form, value):
        if not isinstance(form, list):
            if isinstance(form, Opaque):
                return DROP
            if isinstance(form, Sym) and re.fullmatch(r"L\d+", form):
                return DROP  # static data the dump couldn't print
            return form
        if not form:
            return form
        head, args = form[0], form[1:]
        if head == QUOTE:
            return self.quoted(args[0])
        name = str(head) if isinstance(head, Sym) else ""
        if name == "begin":
            return self.seq(args, value)
        if name in ("when", "unless"):
            cond = self.cond_value(args[0])
            if name == "unless":
                cond = self.negate(cond)
            return self.make_when(cond, args[1:], value)
        if name == "if":
            cond = self.cond_value(args[0])
            t = truth(cond)
            then = self.tr(args[1], value)
            other = self.tr(args[2], value) if len(args) > 2 else (FALSE if value else DROP)
            if t is True:
                return then
            if t is False:
                return other
            if then is DROP and other is DROP:
                return DROP
            return [Sym("if"), cond, FALSE if then is DROP else then] + (
                [] if other is DROP else [other])
        if name == "cond":
            return self.make_cond(args, value)
        if name in ("and", "or"):
            return self.logic(name, args)
        if name == "not":
            return self.negate(self.cond_value(args[0]))
        if name in self.pair.DROPPED_CALLS:
            return FALSE if value else DROP
        handler = getattr(self, "f_" + name.replace("-", "_").replace("?", "_p").replace("!", "_x"),
                          None)
        if handler:
            return handler(args, value)
        # comparisons and other calls: kept, unless one of their arguments is lost
        targs = [self.tr(a, True) for a in args]
        if any(a is DROP for a in targs):
            return FALSE if value else DROP
        return [head] + targs

    def cond_value(self, form):
        t = self.tr(form, True)
        return FALSE if t is DROP else t

    def negate(self, cond):
        t = truth(cond)
        if t is not None:
            return FALSE if t else TRUE
        if isinstance(cond, list) and cond[:1] == [Sym("not")]:
            return cond[1]
        return [Sym("not"), cond]

    def make_when(self, cond, body, value):
        t = truth(cond)
        if t is False:
            return FALSE if value else DROP
        out = self.body(body, value)
        if t is True:
            if not out:
                return FALSE if value else DROP
            return out[0] if len(out) == 1 else [Sym("begin")] + out
        if not out or (value and out == [FALSE]):
            return FALSE if value else DROP
        return [Sym("when"), cond] + out

    def make_cond(self, clauses, value):
        out = []
        for clause in clauses:
            cond = TRUE if clause[0] == Sym("else") else self.cond_value(clause[0])
            t = truth(cond)
            if t is False:
                continue
            # a clause without a body returns its test
            body = self.body(clause[1:], value) if clause[1:] else ([cond] if value else [])
            if t is True:
                if not out:
                    if not body:
                        return FALSE if value else DROP
                    return body[0] if len(body) == 1 else [Sym("begin")] + body
                out.append([Sym("else")] + (body or [FALSE]))
                break
            # a test only known at runtime is kept even with an empty body: it stops the clauses
            # after it
            out.append([cond] + (body or [FALSE]))
        if not out:
            return FALSE if value else DROP
        if not value and all(all(no_effect(f) for f in c[1:]) for c in out):
            return DROP
        return [Sym("cond")] + out

    def logic(self, name, args):
        out = []
        for a in args:
            c = self.cond_value(a)
            t = truth(c)
            if t is (name == "or"):
                return TRUE if name == "or" else FALSE
            if t is not None:
                continue
            out.append(c)
        if not out:
            return TRUE if name == "and" else FALSE
        if len(out) == 1:
            return out[0]
        return [Sym(name)] + out

    def quoted(self, x):
        """A quoted list of levels (a door's on-notice) is mapped, and so is a warp gate's
        destination ('("continue-name" on-activate wait-for), its on-notice), anything else is
        kept."""
        if isinstance(x, list) and x and all(isinstance(i, Sym) for i in x) and any(
                str(i) in self.all_levels for i in x):
            if self.strict_levels is not None and any(
                    str(i) in self.all_levels and str(i) not in self.level_map
                    and str(i) not in self.strict_levels for i in x):
                return FALSE
            levels = self.level_list(x)
            return [QUOTE, [Sym(lv) for lv in levels]] if levels else FALSE
        if isinstance(x, list) and x and isinstance(x[0], Str):
            ours = self.continues.get(str(x[0]))
            return [QUOTE, [Str(ours)] + x[1:]] if ours else FALSE
        return [QUOTE, x]

    # calls #######################################################################################

    def f_want_load(self, args, value):
        levels = with_hubs(self.level_list(args), self.hubs)
        if not levels:
            return DROP
        return [Sym("want-load")] + [[QUOTE, Sym(lv)] for lv in levels]

    def f_want_display(self, args, value):
        lev = self.level(args[0])
        if not lev:
            return DROP
        source = str(args[0][1] if is_quoted(args[0]) else args[0])
        if lev == self.owner and source != self.source:
            # the source game showed and hid levels around this spot while the one holding it
            # stayed: they're one level here (the levels merged into a place), always shown while
            # Jak is in it
            return DROP
        mode = args[1] if len(args) > 1 else [QUOTE, Sym("display")]
        # 'display, 'special (drawn as a backdrop and running, like the mountain seen from Haven
        # Forest, whose platform Jak rides there), else hidden
        if is_quoted(mode) and mode[1] in (Sym("display"), Sym("special")):
            return [Sym("want-display"), [QUOTE, Sym(lev)], [QUOTE, mode[1]]]
        return [Sym("want-display"), [QUOTE, Sym(lev)], FALSE]

    def f_want_vis(self, args, value):
        lev = self.level(args[0])
        if not lev or lev in self.hubs.values():
            # a hub is never the level Jak is in (it's not-physical, like Jak 3's ctywide): the
            # engine would take any other active level for his current level instead
            return DROP
        return [Sym("want-vis"), [QUOTE, Sym(lev)]]

    def f_want_sound(self, args, value):
        """The source game's sound banks, renamed (steps/sound.py)."""
        if not self.sound:
            return DROP
        banks = [self.sound.bank(str(a[1])) if is_quoted(a) else None for a in args]
        return [Sym("want-sound")] + [[QUOTE, Sym(b)] if b else FALSE for b in banks]

    def f_sound_play_loop(self, args, value):
        """A looped ambience: its sound is in the source game's banks, kept with its name."""
        if not self.sound:
            return DROP
        targs = [self.tr(a, True) for a in args]
        return DROP if any(a is DROP for a in targs) else [Sym("sound-play-loop")] + targs

    def f_want_continue(self, args, value):
        ours = self.continues.get(str(args[0]))
        if not ours:
            return DROP
        return [Sym("want-continue"), Str(ours)]

    def f_task_closed_p(self, args, value):
        return TRUE if self.story(str(args[0])) else FALSE

    def f_task_open_p(self, args, value):
        return FALSE if self.story(str(args[0])) else TRUE

    def f_task_complete_p(self, args, value):
        return TRUE

    def f_focus_test_p(self, args, value):
        if any(str(a) in self.pair.ABSENT_FOCUS for a in args[1:]):
            return FALSE  # e.g. no mech in the port
        return [Sym("focus-test?")] + list(args)

    def f_movie_p(self, args, value):
        return [Sym("movie?")]

    def f_setting_pers(self, args, value):
        """Only the fixed camera setting, when its camera is ported:
        (setting-pers entity-name mode "camera-66")"""
        lost = FALSE if value else DROP
        if (len(args) == 3 and args[0] == Sym("entity-name") and args[1] == Sym("mode") and
                isinstance(args[2], Str) and str(args[2]) in self.cameras):
            return [Sym("setting-pers")] + list(args)
        return lost

    def f_send_event(self, args, value):
        lost = FALSE if value else DROP
        target = args[0]
        event = args[1] if len(args) > 1 else None
        ev = str(event[1]) if is_quoted(event) else None
        rest = args[2:]
        if isinstance(target, Opaque) or any(isinstance(a, Opaque) for a in rest):
            return lost
        if target == Sym("self"):
            if ev == "use-camera":
                # an elevator's ride camera: kept if ported, (use-camera #f) gives it back
                cam = rest[0] if rest else FALSE
                if cam == FALSE or (isinstance(cam, Str) and str(cam) in self.cameras):
                    return [Sym("send-event")] + list(args)
                return lost
            if ev not in self.pair.KEPT_SELF_EVENTS:
                return lost
            if ev == "query" and not (rest and is_quoted(rest[0]) and
                                      str(rest[0][1]) in self.pair.KEPT_QUERIES):
                return lost
            return [Sym("send-event")] + list(args)
        name = self.renames.get(str(target))
        if not name or ev not in self.pair.KEPT_OTHER_EVENTS:
            return lost
        if (ev, dump(rest[0]) if rest else None) in self.drop_events:
            return lost
        return [Sym("send-event"), Str(name)] + list(args[1:])


if __name__ == "__main__":
    # with_hubs self-check: Jak 2's Dead Town airlock loads the ruins with the slums district only;
    # the district's hub comes first
    hubs = {"hj2-slmb": "havenj2", "hj2-slma": "havenj2"}
    assert with_hubs(["hj2-slmb", "hj2-ruins"], hubs) == ["havenj2", "hj2-slmb", "hj2-ruins"]
    assert with_hubs(["hj2-slma", "havenj2", "hj2-slmb"], hubs) == ["havenj2", "hj2-slma", "hj2-slmb"]
    assert with_hubs(["hj2-ruins"], hubs) == ["hj2-ruins"]
    print("ok")
