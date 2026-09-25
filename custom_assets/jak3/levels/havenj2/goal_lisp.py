"""A small reader and printer for GOAL source code, used to translate Jak 2's decompiled particle
definitions (defpart, defpartgroup) for Jak 3 (gen_havenj2_particles.py).

Forms are Python lists; atoms are Atom (symbols, numbers, keywords, #x/#b literals, kept as their
source text) or Str (string literals). 'x reads as [Atom("quote"), x].
"""

import re


class Atom(str):
    """A symbol, number or other literal, as written."""


class Str(str):
    """A string literal (without its quotes)."""


QUOTE = Atom("quote")
TOKEN = re.compile(r"""\s*(?:(;[^\n]*)|(#\|.*?\|#)|(\()|(\))|(')|("(?:[^"\\]|\\.)*")|([^\s()'";]+))""",
                   re.S)


def read_all(text):
    """Every top-level form of a source file."""
    pos = 0

    def token():
        nonlocal pos
        while True:
            m = TOKEN.match(text, pos)
            if not m or m.end() == pos:
                return None
            pos = m.end()
            if m.group(1) or m.group(2):
                continue  # comment
            return m

    def read(m):
        lpar, rpar, quote, string, atom = m.groups()[2:]
        if lpar:
            items = []
            while True:
                t = token()
                if t is None:
                    raise ValueError("unbalanced parentheses")
                if t.group(4):
                    return items
                items.append(read(t))
        if rpar:
            raise ValueError(f"unexpected ) at {pos}")
        if quote:
            return [QUOTE, read(token())]
        if string is not None:
            return Str(string[1:-1])
        return Atom(atom)

    forms = []
    while True:
        t = token()
        if t is None:
            break
        forms.append(read(t))
    if text[pos:].strip():
        raise ValueError(f"can't read {text[pos:pos + 40]!r}")
    return forms


def dump(form):
    """One line."""
    if isinstance(form, list):
        if len(form) == 2 and form[0] == QUOTE:
            return "'" + dump(form[1])
        return "(" + " ".join(dump(f) for f in form) + ")"
    if isinstance(form, Str):
        return '"' + form + '"'
    return str(form)


def pretty(form, indent=0, width=100):
    """A readable multi-line print: a list that doesn't fit on the line puts its head and first
    arguments on the first line and the rest one per line."""
    one = dump(form)
    if not isinstance(form, list) or len(one) + indent <= width or len(form) < 2:
        return one
    if form[0] == QUOTE:
        return "'" + pretty(form[1], indent + 1, width)
    pad = " " * (indent + 2)
    head = dump(form[0])
    lines = ["(" + head]
    rest = form[1:]
    # keep keyword/value pairs together
    i = 0
    items = []
    while i < len(rest):
        if isinstance(rest[i], Atom) and rest[i].startswith(":") and i + 1 < len(rest):
            items.append((rest[i], rest[i + 1]))
            i += 2
        else:
            items.append((None, rest[i]))
            i += 1
    for key, value in items:
        if key is None:
            lines.append(pad + pretty(value, indent + 2, width))
        else:
            lines.append(pad + str(key) + " " + pretty(value, indent + 3 + len(key), width))
    return "\n".join(lines) + "\n" + " " * indent + ")"


def is_list(form, head=None):
    return isinstance(form, list) and form and (head is None or form[0] == Atom(head))


def keyword_args(form, start):
    """{":key": value} of a form's keyword arguments from index start."""
    out = {}
    i = start
    while i + 1 < len(form):
        if isinstance(form[i], Atom) and form[i].startswith(":"):
            out[str(form[i])] = form[i + 1]
            i += 2
        else:
            i += 1
    return out


def parse_int(atom):
    """An integer literal (decimal, #x, #b), or None."""
    s = str(atom)
    try:
        if s.startswith("#x"):
            return int(s[2:], 16)
        if s.startswith("#b"):
            return int(s[2:], 2)
        if re.fullmatch(r"-?\d+", s):
            return int(s)
    except ValueError:
        return None
    return None
