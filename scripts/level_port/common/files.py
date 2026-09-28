"""Files: the repository root, JSON with comments, and writing generated files."""

import json
import os
import re

# the repository root (scripts/level_port/common/files.py)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

_JSONC_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|//[^\n]*|/\*.*?\*/', re.S)


def read_jsonc(path):
    """A JSON file that may hold // and /* */ comments (like the level .jsonc files)."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    return json.loads(_JSONC_TOKEN.sub(lambda m: m.group(0) if m.group(0)[0] == '"' else "", text))


def write_if_changed(path, data):
    """Write a generated file only when its content changes (text is written as UTF-8 with the line
    ends it has). goalc's make rebuilds a level whenever one of its inputs is newer than its output,
    and the port rewrites every level it knows: an unchanged level keeps its date."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if os.path.exists(path):
        with open(path, "rb") as f:
            if f.read() == data:
                return False
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return True
