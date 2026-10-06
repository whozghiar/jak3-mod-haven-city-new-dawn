"""The port's steps, run in this order by __main__.py. The first checks the games' extractions
(and makes what is missing); each other reads the manifest and writes its part of the levels:
background meshes (with the pools), ocean maps, navigation data, then the levels themselves (their
actors, particles, models, regions, continues, sound and level files)."""

from . import extract, levels, mesh, nav, ocean

STEPS = {
    "extract": extract.run,
    "mesh": mesh.run,
    "ocean": ocean.run,
    "nav": nav.run,
    "levels": levels.run,
}
