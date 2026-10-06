"""The port's steps, run in this order by __main__.py. Each one reads the manifest and writes its
part of the levels: background meshes (with the pools), ocean maps, navigation data, then the levels
themselves (their actors, particles, models, regions, continues and level files)."""

from . import levels, mesh, nav, ocean

STEPS = {
    "mesh": mesh.run,
    "ocean": ocean.run,
    "nav": nav.run,
    "levels": levels.run,
}
