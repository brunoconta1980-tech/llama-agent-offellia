#!/usr/bin/env python3
"""Write SVG, PPM, and GLB game files with the Python standard library."""

import argparse
import json
import struct
import sys
import tempfile
from pathlib import Path


def svg_header(width, height):
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"%d\" height=\"%d\" viewBox=\"0 0 %d %d\">\n"
        % (width, height, width, height)
    )


def write_icon(path, label, size):
    text = label[:2] if label else ""
    body = svg_header(size, size)
    body += "<rect x=\"1\" y=\"1\" width=\"%d\" height=\"%d\" fill=\"none\" stroke=\"#222\" stroke-width=\"2\"/>\n" % (size - 2, size - 2)
    if text:
        body += "<text x=\"50%%\" y=\"54%%\" text-anchor=\"middle\" font-family=\"sans-serif\" font-size=\"%d\" fill=\"#222\">%s</text>\n" % (
            max(8, size // 2), text.replace("&", "&amp;").replace("<", "&lt;"))
    body += "</svg>\n"
    Path(path).write_text(body, encoding="utf-8")
    print("icon %s %dx%d" % (path, size, size))


def write_sheet(path, frames, size):
    width = frames * size
    body = svg_header(width, size)
    for index in range(frames):
        x = index * size
        pad = max(1, size // 8)
        body += "<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"#%02x%02x%02x\"/>\n" % (
            x + pad, pad, size - 2 * pad, size - 2 * pad,
            40 + index * 30, 80, 160,
        )
        # A marker that moves so frames are not identical.
        mark = pad + int((size - 3 * pad) * index / max(1, frames - 1))
        body += "<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"#fff\"/>\n" % (
            x + mark, size // 2, pad, pad)
    body += "</svg>\n"
    Path(path).write_text(body, encoding="utf-8")
    print("sheet %s frames=%d frame=%d" % (path, frames, size))


def write_tileset(path, cols, rows, tile):
    body = svg_header(cols * tile, rows * tile)
    for row in range(rows):
        for col in range(cols):
            x = col * tile
            y = row * tile
            shade = 40 + ((row * cols + col) * 17) % 180
            body += "<rect x=\"%d\" y=\"%d\" width=\"%d\" height=\"%d\" fill=\"#%02x%02x%02x\" stroke=\"#111\"/>\n" % (
                x, y, tile, tile, shade, 90, 70)
    body += "</svg>\n"
    Path(path).write_text(body, encoding="utf-8")
    print("tileset %s %dx%d tile=%d" % (path, cols, rows, tile))


def write_ppm(path, size):
    pixels = bytearray()
    for y in range(size):
        for x in range(size):
            pixels += bytes((x * 255 // max(1, size - 1), y * 255 // max(1, size - 1), 96))
    Path(path).write_bytes(b"P6\n%d %d\n255\n" % (size, size) + bytes(pixels))
    print("ppm %s %dx%d" % (path, size, size))


def write_glb(path):
    positions = [
        -0.5, -0.5, -0.5,  0.5, -0.5, -0.5,  0.5, 0.5, -0.5,  -0.5, 0.5, -0.5,
        -0.5, -0.5,  0.5,  0.5, -0.5,  0.5,  0.5, 0.5,  0.5,  -0.5, 0.5,  0.5,
    ]
    indices = [
        4, 5, 6, 6, 7, 4,
        1, 0, 3, 3, 2, 1,
        5, 1, 2, 2, 6, 5,
        0, 4, 7, 7, 3, 0,
        3, 7, 6, 6, 2, 3,
        0, 1, 5, 5, 4, 0,
    ]
    pos_blob = struct.pack("<" + "f" * len(positions), *positions)
    idx_blob = struct.pack("<" + "H" * len(indices), *indices)
    blob = pos_blob + idx_blob
    document = {
        "asset": {"version": "2.0", "generator": "llama-agent-game-assets"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "Box"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "accessors": [
            {
                "bufferView": 0, "componentType": 5126, "count": 8, "type": "VEC3",
                "min": [-0.5, -0.5, -0.5], "max": [0.5, 0.5, 0.5],
            },
            {"bufferView": 1, "componentType": 5123, "count": len(indices), "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(pos_blob), "target": 34962},
            {"buffer": 0, "byteOffset": len(pos_blob), "byteLength": len(idx_blob), "target": 34963},
        ],
        "buffers": [{"byteLength": len(blob)}],
    }
    json_chunk = json.dumps(document, separators=(",", ":")).encode("utf-8")
    while len(json_chunk) % 4:
        json_chunk += b" "
    while len(blob) % 4:
        blob += b"\x00"
    total = 12 + 8 + len(json_chunk) + 8 + len(blob)
    data = bytearray()
    data += struct.pack("<4sII", b"glTF", 2, total)
    data += struct.pack("<I4s", len(json_chunk), b"JSON")
    data += json_chunk
    data += struct.pack("<I4s", len(blob), b"BIN\x00")
    data += blob
    Path(path).write_bytes(data)
    print("glb %s bytes=%d triangles=%d" % (path, len(data), len(indices) // 3))


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_icon(root / "icon.svg", "S", 32)
        write_sheet(root / "walk.svg", 4, 16)
        write_tileset(root / "tiles.svg", 2, 2, 8)
        write_ppm(root / "tile.ppm", 4)
        write_glb(root / "box.glb")
        icon = (root / "icon.svg").read_text(encoding="utf-8")
        if "svg" not in icon or "S" not in icon:
            raise SystemExit("icon missing label")
        ppm = (root / "tile.ppm").read_bytes()
        if not ppm.startswith(b"P6\n4 4\n255\n") or len(ppm) != len(b"P6\n4 4\n255\n") + 4 * 4 * 3:
            raise SystemExit("ppm size mismatch")
        blob = (root / "box.glb").read_bytes()
        magic, version, length = struct.unpack_from("<4sII", blob, 0)
        if magic != b"glTF" or version != 2 or length != len(blob):
            raise SystemExit("bad glb header")
        json_len = struct.unpack_from("<I", blob, 12)[0]
        document = json.loads(blob[20:20 + json_len])
        if document["accessors"][1]["count"] != 36:
            raise SystemExit("unexpected index count")
    print("self-test ok")


def main(argv):
    if argv == ["--self-test"]:
        self_test()
        return 0
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    icon = sub.add_parser("icon")
    icon.add_argument("--out", required=True)
    icon.add_argument("--label", default="")
    icon.add_argument("--size", type=int, default=64)
    sheet = sub.add_parser("sheet")
    sheet.add_argument("--out", required=True)
    sheet.add_argument("--frames", type=int, default=4)
    sheet.add_argument("--size", type=int, default=32)
    tiles = sub.add_parser("tileset")
    tiles.add_argument("--out", required=True)
    tiles.add_argument("--cols", type=int, default=4)
    tiles.add_argument("--rows", type=int, default=4)
    tiles.add_argument("--tile", type=int, default=32)
    ppm = sub.add_parser("ppm")
    ppm.add_argument("--out", required=True)
    ppm.add_argument("--size", type=int, default=16)
    glb = sub.add_parser("glb")
    glb.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "icon":
        write_icon(args.out, args.label, args.size)
    elif args.command == "sheet":
        write_sheet(args.out, args.frames, args.size)
    elif args.command == "tileset":
        write_tileset(args.out, args.cols, args.rows, args.tile)
    elif args.command == "ppm":
        write_ppm(args.out, args.size)
    else:
        write_glb(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
