#!/usr/bin/env python3
"""Numeric checks for y-up, right-handed frames. No engine import."""

import math
import sys


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(v):
    length = math.sqrt(dot(v, v))
    return (v[0] / length, v[1] / length, v[2] / length)


def yaw_to_face_negative_z(direction):
    """rotation.y that points a -z-fronted object along direction."""
    return math.atan2(-direction[0], -direction[2])


def local_forward_after_yaw(yaw):
    """Where local -z goes after rotation.y (y-up)."""
    return norm((-math.sin(yaw), 0.0, -math.cos(yaw)))


def yaw_from_planar_angle(phi):
    """Top-down: a 2D angle phi = atan2(z, x) becomes rotation.y = -phi."""
    return -phi


def local_plus_x_after_yaw(yaw):
    return (math.cos(yaw), 0.0, -math.sin(yaw))


def check(name, cond):
    if not cond:
        print("FAIL %s" % name)
        return 1
    print("PASS %s" % name)
    return 0


def main():
    failed = 0
    forward = (0.0, 0.0, -1.0)
    up = (0.0, 1.0, 0.0)
    right = cross(forward, up)
    left = cross(up, forward)
    failed += check("forward x up = +x", all(abs(a - b) < 1e-9 for a, b in zip(right, (1.0, 0.0, 0.0))))
    failed += check("up x forward = -x", all(abs(a - b) < 1e-9 for a, b in zip(left, (-1.0, 0.0, 0.0))))

    identity = yaw_to_face_negative_z((0.0, 0.0, -1.0))
    failed += check("facing -z keeps yaw 0", abs(identity) < 1e-9)
    plus_x = yaw_to_face_negative_z((1.0, 0.0, 0.0))
    landed = local_forward_after_yaw(plus_x)
    failed += check("yaw faces +x", dot(landed, (1.0, 0.0, 0.0)) > 0.999)

    phi = math.atan2(1.0, 0.0)  # +z in the ground plane
    yaw = yaw_from_planar_angle(phi)
    moved = local_plus_x_after_yaw(yaw)
    # [[c, -s], [s, c]] applied to +x is (cos phi, sin phi) = (0, 1) in (x, z)
    failed += check("planar +z maps through negated yaw", abs(moved[0] - 0.0) < 1e-9 and abs(moved[2] - 1.0) < 1e-9)

    # lookAt points +z at the target. A -z-fronted body must add pi, which is not lookAt alone.
    look_at_faces_plus_z = (0.0, 0.0, 1.0)
    failed += check("lookAt +z is not character forward", dot(look_at_faces_plus_z, forward) < -0.999)

    if failed:
        print("%d checks failed" % failed)
        return 1
    print("frame checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
