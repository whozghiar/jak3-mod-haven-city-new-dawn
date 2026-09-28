"""Geometry shared by the steps: rotations, bounding spheres, region faces, matrices."""

import math


def r4(x):
    return round(x, 4)


def quat_rotate(q, v):
    """v rotated by the quaternion q = (x, y, z, w), like GOAL's quaternion->matrix applied to a
    point."""
    x, y, z, w = q
    # t = 2 * cross(q.xyz, v); v' = v + w * t + cross(q.xyz, t)
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx))


def front(actor):
    """Where an actor faces (its z axis), in world space."""
    return quat_rotate(actor["quat"], [0.0, 0.0, 1.0])


def normalize(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


def yaw_quat(fx, fz):
    """The rotation around y facing (fx, fz)."""
    yaw = math.atan2(fx, fz)
    return [0.0, math.sin(yaw / 2), 0.0, math.cos(yaw / 2)]


def bounding_sphere(points, pad=0.0):
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    center = [(lo[i] + hi[i]) / 2 for i in range(3)]
    radius = max(math.dist(center, p) for p in points)
    return [r4(c) for c in center] + [r4(radius + pad)]


# boxes ###########################################################################################

BOX_QUADS = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]


def box_corners(lo, hi):
    return [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


# region faces ####################################################################################
# A region volume is a list of faces, each a plane (normal and distance, outside where
# dot(p, n) > d) and its points. The game's inside test only uses the planes.


def face(normal, points):
    d = sum(normal[i] * points[0][i] for i in range(3))
    return {"normal": [round(c, 6) for c in normal] + [round(d, 6)],
            "points": [[round(c, 6) for c in p] for p in points]}


def box_faces(lo, hi):
    """Outward faces of an axis-aligned box."""
    faces = []
    for axis in range(3):
        u, v = [i for i in range(3) if i != axis]
        for sign, value in ((1.0, hi[axis]), (-1.0, lo[axis])):
            normal = [0.0, 0.0, 0.0]
            normal[axis] = sign
            points = []
            for a in (lo[u], hi[u]):
                for b in (lo[v], hi[v]):
                    p = [0.0, 0.0, 0.0]
                    p[axis], p[u], p[v] = value, a, b
                    points.append(p)
            faces.append(face(normal, points))
    return faces


def convex_hull_xz(points):
    """Counter-clockwise convex hull (monotone chain) of (x, z) points."""
    pts = sorted(set((round(p[0], 3), round(p[1], 3)) for p in points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def prism_faces(hull, lo_y, hi_y):
    """Outward faces of the vertical prism with the given xz hull, between lo_y and hi_y, its center
    and radius."""
    cx = sum(p[0] for p in hull) / len(hull)
    cz = sum(p[1] for p in hull) / len(hull)
    faces = [face([0.0, 1.0, 0.0], [[p[0], hi_y, p[1]] for p in hull]),
             face([0.0, -1.0, 0.0], [[p[0], lo_y, p[1]] for p in hull])]
    for i in range(len(hull)):
        a, b = hull[i], hull[(i + 1) % len(hull)]
        nx, nz = b[1] - a[1], -(b[0] - a[0])
        length = math.hypot(nx, nz)
        nx, nz = nx / length, nz / length
        if nx * (a[0] - cx) + nz * (a[1] - cz) < 0:
            nx, nz = -nx, -nz
        faces.append(face([nx, 0.0, nz], [[a[0], lo_y, a[1]], [a[0], hi_y, a[1]],
                                          [b[0], lo_y, b[1]], [b[0], hi_y, b[1]]]))
    center = [cx, (lo_y + hi_y) / 2, cz]
    radius = max(math.dist(center, [p[0], y, p[1]]) for p in hull for y in (lo_y, hi_y))
    return faces, center, radius


# matrices (4x4, as rows) #########################################################################


def mat_from_gltf(m):
    """A glTF matrix (16 floats, column major) as rows."""
    return [[m[c * 4 + r] for c in range(4)] for r in range(4)]


def mat_mul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def mat_inverse(m):
    """Gauss-Jordan inverse."""
    a = [list(row) + [1.0 if i == j else 0.0 for j in range(4)] for i, row in enumerate(m)]
    for col in range(4):
        pivot = max(range(col, 4), key=lambda r: abs(a[r][col]))
        a[col], a[pivot] = a[pivot], a[col]
        f = a[col][col]
        a[col] = [x / f for x in a[col]]
        for r in range(4):
            if r != col and a[r][col] != 0.0:
                g = a[r][col]
                a[r] = [x - g * y for x, y in zip(a[r], a[col])]
    return [row[4:] for row in a]


def mat_decompose(m):
    """(translation, rotation quaternion x y z w, scale) of an affine matrix."""
    trans = [m[0][3], m[1][3], m[2][3]]
    cols = [[m[r][c] for r in range(3)] for c in range(3)]
    scale = [math.sqrt(sum(x * x for x in col)) or 1.0 for col in cols]
    r = [[cols[c][row] / scale[c] for c in range(3)] for row in range(3)]
    tr = r[0][0] + r[1][1] + r[2][2]
    if tr > 0:
        s4 = math.sqrt(tr + 1.0) * 2
        q = [(r[2][1] - r[1][2]) / s4, (r[0][2] - r[2][0]) / s4, (r[1][0] - r[0][1]) / s4, 0.25 * s4]
    elif r[0][0] > r[1][1] and r[0][0] > r[2][2]:
        s4 = math.sqrt(1.0 + r[0][0] - r[1][1] - r[2][2]) * 2
        q = [0.25 * s4, (r[0][1] + r[1][0]) / s4, (r[0][2] + r[2][0]) / s4, (r[2][1] - r[1][2]) / s4]
    elif r[1][1] > r[2][2]:
        s4 = math.sqrt(1.0 + r[1][1] - r[0][0] - r[2][2]) * 2
        q = [(r[0][1] + r[1][0]) / s4, 0.25 * s4, (r[1][2] + r[2][1]) / s4, (r[0][2] - r[2][0]) / s4]
    else:
        s4 = math.sqrt(1.0 + r[2][2] - r[0][0] - r[1][1]) * 2
        q = [(r[0][2] + r[2][0]) / s4, (r[1][2] + r[2][1]) / s4, 0.25 * s4, (r[1][0] - r[0][1]) / s4]
    n = math.sqrt(sum(x * x for x in q)) or 1.0
    return trans, [x / n for x in q], scale
