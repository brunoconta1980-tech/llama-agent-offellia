#!/usr/bin/env python3
"""Create and read .docx files with the Python standard library."""

import argparse
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def paragraph(text, style=None):
    props = ""
    if style:
        props = "<w:pPr><w:pStyle w:val=\"%s\"/></w:pPr>" % style
    return "<w:p>%s<w:r><w:t xml:space=\"preserve\">%s</w:t></w:r></w:p>" % (props, escape(text))


def table(rows):
    xml = ["<w:tbl>"]
    for row in rows:
        xml.append("<w:tr>")
        for cell in row:
            xml.append("<w:tc><w:p><w:r><w:t xml:space=\"preserve\">%s</w:t></w:r></w:p></w:tc>" % escape(cell))
        xml.append("</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml)


def parse_markdown(text):
    blocks = []
    paragraph_lines = []
    table_rows = []

    def flush_paragraph():
        if paragraph_lines:
            blocks.append(("p", " ".join(paragraph_lines).strip()))
            paragraph_lines.clear()

    def flush_table():
        if table_rows:
            blocks.append(("table", list(table_rows)))
            table_rows.clear()

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush_paragraph()
            flush_table()
            continue
        if "|" in line and line.strip().startswith("|"):
            flush_paragraph()
            cells = [part.strip() for part in line.strip().strip("|").split("|")]
            if cells and set("".join(cells)) <= set("-: "):
                continue
            table_rows.append(cells)
            continue
        flush_table()
        if line.startswith("### "):
            flush_paragraph()
            blocks.append(("h3", line[4:].strip()))
        elif line.startswith("## "):
            flush_paragraph()
            blocks.append(("h2", line[3:].strip()))
        elif line.startswith("# "):
            flush_paragraph()
            blocks.append(("h1", line[2:].strip()))
        elif line.startswith("- ") or line.startswith("* "):
            flush_paragraph()
            blocks.append(("li", line[2:].strip()))
        else:
            paragraph_lines.append(line.strip())
    flush_paragraph()
    flush_table()
    return blocks


def document_xml(blocks):
    style = {"h1": "Heading1", "h2": "Heading2", "h3": "Heading3", "li": "ListParagraph"}
    parts = []
    for kind, value in blocks:
        if kind == "table":
            parts.append(table(value))
        else:
            parts.append(paragraph(value, style.get(kind)))
    if not parts:
        parts.append(paragraph(""))
    body = "".join(parts)
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"%s\"><w:body>%s"
        "<w:sectPr><w:pgSz w:w=\"12240\" w:h=\"15840\"/>"
        "<w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\"/>"
        "</w:sectPr></w:body></w:document>"
    ) % (W, body)


CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>
"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""

STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="%s">
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:rPr><w:b/><w:sz w:val="26"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:rPr><w:b/><w:sz w:val="22"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/></w:style>
</w:styles>
""" % W


def write_docx(path, markdown):
    blocks = parse_markdown(markdown)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES)
        archive.writestr("_rels/.rels", RELS)
        archive.writestr("word/document.xml", document_xml(blocks))
        archive.writestr("word/_rels/document.xml.rels", DOC_RELS)
        archive.writestr("word/styles.xml", STYLES)
    return len(blocks)


def read_text(path):
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    lines = []
    for node in root.iter("{%s}t" % W):
        if node.text:
            lines.append(node.text)
    return "\n".join(lines)


def self_test():
    sample = "# Title\n\nHello & world.\n\n- One\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "note.docx"
        count = write_docx(out, sample)
        if count < 4:
            raise SystemExit("expected blocks, got %s" % count)
        text = read_text(out)
        for needle in ("Title", "Hello & world.", "One", "A", "2"):
            if needle not in text:
                raise SystemExit("missing %r in %r" % (needle, text))
        with zipfile.ZipFile(out) as archive:
            ET.fromstring(archive.read("[Content_Types].xml"))
            ET.fromstring(archive.read("word/document.xml"))
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
    read = sub.add_parser("text")
    read.add_argument("docx")
    args = parser.parse_args(argv)
    if args.command == "create":
        markdown = Path(args.input).read_text(encoding="utf-8")
        count = write_docx(args.out, markdown)
        print("wrote %s (%d blocks)" % (args.out, count))
    else:
        sys.stdout.write(read_text(args.docx))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
