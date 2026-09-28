"""Convex hulls, for the collision of the models rebuilt from ripped ones (glb.rebuild_model).

A game's actors collide with meshes of their art groups, which the model rips don't have. The hull
of a model's vertices stands in for them: build-actor makes a collide mesh of it (at most 255
vertices, so the hull is taken over the model's extreme points in a set of directions).
"""

import math


def directions(count):
    """count directions spread over the sphere (Fibonacci lattice), plus the 6 axes."""
    out = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(count):
        y = 1.0 - 2.0 * (i + 0.5) / count
        r = math.sqrt(max(0.0, 1.0 - y * y))
        a = golden * i
        out.append((math.cos(a) * r, y, math.sin(a) * r))
    return out


def extreme_points(points, count=160):
    """The points furthest along each of count directions (duplicates removed)."""
    keep = []
    for d in directions(count):
        best = max(points, key=lambda p: p[0] * d[0] + p[1] * d[1] + p[2] * d[2])
        if best not in keep:
            keep.append(best)
    return keep


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def convex_hull(points, eps=1e-6):
    """Triangles (i, j, k) of the convex hull of points, wound counterclockwise seen from outside
    (incremental algorithm). Points inside or on the hull are left out."""
    pts = list(points)
    n = len(pts)
    if n < 4:
        raise ValueError("a hull needs 4 points")
    # a first tetrahedron: two far apart points, the furthest from their line, then from their plane
    i0 = min(range(n), key=lambda i: pts[i])
    i1 = max(range(n), key=lambda i: _dot(_sub(pts[i], pts[i0]), _sub(pts[i], pts[i0])))

    def line_dist(i):
        c = _cross(_sub(pts[i1], pts[i0]), _sub(pts[i], pts[i0]))
        return _dot(c, c)
    i2 = max(range(n), key=line_dist)
    normal = _cross(_sub(pts[i1], pts[i0]), _sub(pts[i2], pts[i0]))
    i3 = max(range(n), key=lambda i: abs(_dot(normal, _sub(pts[i], pts[i0]))))
    if abs(_dot(normal, _sub(pts[i3], pts[i0]))) < eps:
        raise ValueError("flat point set")

    faces = {}  # (a, b, c) -> (normal, offset)

    def add_face(a, b, c):
        nrm = _cross(_sub(pts[b], pts[a]), _sub(pts[c], pts[a]))
        faces[(a, b, c)] = (nrm, _dot(nrm, pts[a]))

    center = tuple(sum(pts[i][k] for i in (i0, i1, i2, i3)) / 4.0 for k in range(3))
    for a, b, c in ((i0, i1, i2), (i0, i1, i3), (i0, i2, i3), (i1, i2, i3)):
        nrm = _cross(_sub(pts[b], pts[a]), _sub(pts[c], pts[a]))
        if _dot(nrm, _sub(center, pts[a])) > 0:
            a, b = b, a
        add_face(a, b, c)

    for p in range(n):
        if p in (i0, i1, i2, i3):
            continue
        visible = [f for f, (nrm, off) in faces.items()
                   if _dot(nrm, pts[p]) - off > eps * math.sqrt(_dot(nrm, nrm))]
        if not visible:
            continue
        edges = set()
        for a, b, c in visible:
            for e in ((a, b), (b, c), (c, a)):
                edges.add(e)
        for f in visible:
            del faces[f]
        # the horizon: edges of the visible faces whose other side isn't visible
        for a, b in edges:
            if (b, a) not in edges:
                add_face(a, b, p)
    return list(faces)


def hull_mesh(points, count=160):
    """(vertices, triangles) of the hull of the extreme points of points."""
    pts = extreme_points(points, count)
    tris = convex_hull(pts)
    used = sorted({i for t in tris for i in t})
    remap = {old: new for new, old in enumerate(used)}
    return [pts[i] for i in used], [tuple(remap[i] for i in t) for t in tris]
