"""Helpers shared by the havenj2 generators."""

import os


def write_if_changed(path, data):
    """Write a generated file only when its content changes (text is written as UTF-8 with the line
    ends it has). goalc's make rebuilds a level whenever one of its inputs is newer than its output,
    and the generators rewrite every level they know: an unchanged level keeps its date."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if os.path.exists(path):
        with open(path, "rb") as f:
            if f.read() == data:
                return False
    with open(path, "wb") as f:
        f.write(data)
    return True
