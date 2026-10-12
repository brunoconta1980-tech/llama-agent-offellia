#!/usr/bin/env python3
"""Create, extract, and merge PDF files. Uses qpdf or pdftotext when they are installed."""

import argparse
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path


def encode_winansi(text):
    encoded = text.encode("cp1252", errors="replace")
    out = []
    for byte in encoded:
        char = chr(byte)
        if char in "\\()":
            out.append("\\" + char)
        elif byte < 32 or byte > 126:
            out.append("\\%03o" % byte)
        else:
            out.append(char)
    return "".join(out)


def wrap_lines(text, width=90):
    lines = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split()
        current = ""
        for word in words:
            trial = word if not current else current + " " + word
            if len(trial) <= width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines or [""]


def page_stream(lines):
    commands = ["BT", "/F1 11 Tf", "14 TL", "72 740 Td"]
    first = True
    for line in lines:
        if not first:
            commands.append("T*")
        commands.append("(%s) Tj" % encode_winansi(line))
        first = False
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def build_pdf(pages):
    objects = []

    def add(data):
        objects.append(data)
        return len(objects)

    page_ids = []
    content_ids = []
    for lines in pages:
        stream = page_stream(lines)
        content_ids.append(add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"))
    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for content_id in content_ids:
        page_ids.append(add(
            ("<< /Type /Page /Parent 0 0 R /MediaBox [0 0 612 792] "
             "/Contents %d 0 R /Resources << /Font << /F1 %d 0 R >> >> >>" % (content_id, font_id)).encode()
        ))
    kids = " ".join("%d 0 R" % pid for pid in page_ids)
    pages_id = add(("<< /Type /Pages /Count %d /Kids [%s] >>" % (len(page_ids), kids)).encode())
    # Parent references were unknown when pages were written. Rewrite them.
    fixed = []
    for obj in objects:
        fixed.append(obj.replace(b"/Parent 0 0 R", ("/Parent %d 0 R" % pages_id).encode()))
    objects = fixed
    catalog_id = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
    info_id = add(b"<< /Producer (llama-agent-pdf) >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += ("%d 0 obj\n" % index).encode()
        out += obj
        out += b"\nendobj\n"
    xref = len(out)
    out += ("xref\n0 %d\n" % (len(objects) + 1)).encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += ("%010d 00000 n \n" % offset).encode()
    out += ("trailer << /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, catalog_id, info_id, xref)).encode()
    return bytes(out)


def paginate(text, width=90, height=42):
    lines = wrap_lines(text, width)
    return [lines[i:i + height] for i in range(0, len(lines), height)] or [[""]]


def write_pdf(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_pdf(paginate(text)))


def extract_streams(data):
    texts = []
    cursor = 0
    while True:
        start = data.find(b"stream\n", cursor)
        if start < 0:
            break
        start += len(b"stream\n")
        end = data.find(b"\nendstream", start)
        if end < 0:
            break
        raw = data[start:end]
        if raw.startswith(b"\x78"):
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                pass
        texts.append(raw.decode("latin-1", errors="replace"))
        cursor = end + 1
    return texts


def text_from_stream(stream):
    lines = []
    current = []
    i = 0
    while i < len(stream):
        if stream[i] == "(":
            i += 1
            chars = []
            while i < len(stream) and stream[i] != ")":
                if stream[i] == "\\" and i + 1 < len(stream):
                    nxt = stream[i + 1]
                    if nxt in "\\()":
                        chars.append(nxt)
                        i += 2
                        continue
                    if nxt.isdigit():
                        octal = stream[i + 1:i + 4]
                        take = 0
                        while take < len(octal) and octal[take].isdigit():
                            take += 1
                        chars.append(chr(int(octal[:take], 8)))
                        i += 1 + take
                        continue
                chars.append(stream[i])
                i += 1
            current.append("".join(chars))
            if i < len(stream) and stream[i] == ")":
                i += 1
            continue
        if stream.startswith("T*", i) or stream.startswith("ET", i):
            if current:
                lines.append("".join(current))
                current = []
        i += 1
    if current:
        lines.append("".join(current))
    return "\n".join(lines)


def read_text(path):
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        result = subprocess.run([pdftotext, "-layout", str(path), "-"], capture_output=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.decode("utf-8", "replace")
    data = Path(path).read_bytes()
    parts = [text_from_stream(stream) for stream in extract_streams(data)]
    return "\n\n".join(part for part in parts if part.strip())


def merge(paths, out):
    qpdf = shutil.which("qpdf")
    if qpdf:
        cmd = [qpdf, "--empty", "--pages", *paths, "--", out]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip() or "qpdf failed")
        print("merged with qpdf -> %s" % out)
        return
    chunks = []
    for path in paths:
        text = read_text(path).strip()
        chunks.append(text)
    write_pdf(out, "\n\n".join(chunks))
    print("merged extracted text -> %s" % out)


def self_test():
    with tempfile.TemporaryDirectory() as tmp:
        one = Path(tmp) / "a.pdf"
        two = Path(tmp) / "b.pdf"
        merged = Path(tmp) / "c.pdf"
        write_pdf(one, "Alpha page\nLine two")
        write_pdf(two, "Beta (page)")
        got = read_text(one)
        if "Alpha page" not in got or "Line two" not in got:
            raise SystemExit("extract failed: %r" % got)
        merge([str(one), str(two)], str(merged))
        both = read_text(merged)
        if "Alpha page" not in both or "Beta (page)" not in both:
            raise SystemExit("merge failed: %r" % both)
    print("self-test ok")


def main(argv):
    if argv == ["--self-test"]:
        self_test()
        return 0
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--out", required=True)
    create.add_argument("--input", required=True)
    text = sub.add_parser("text")
    text.add_argument("pdf")
    join = sub.add_parser("merge")
    join.add_argument("--out", required=True)
    join.add_argument("pdfs", nargs="+")
    args = parser.parse_args(argv)
    if args.command == "create":
        write_pdf(args.out, Path(args.input).read_text(encoding="utf-8"))
        print("wrote %s" % args.out)
    elif args.command == "text":
        sys.stdout.write(read_text(args.pdf))
        if not read_text(args.pdf).endswith("\n"):
            sys.stdout.write("\n")
    else:
        merge(args.pdfs, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
