#!/usr/bin/env python3
"""Create and read .pptx files with the Python standard library."""

import argparse
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET

NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def slides_from_markdown(text):
    slides = []
    title = None
    body = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("# "):
            if title is not None:
                slides.append((title, body))
            title = line[2:].strip()
            body = []
        elif line.strip():
            if title is None:
                title = line.strip()
            else:
                body.append(line.strip())
    if title is not None:
        slides.append((title, body))
    if not slides:
        raise SystemExit("no slides in input; start a slide with a # heading")
    return slides


def shape(shape_id, name, x, y, cx, cy, text, size):
    paragraphs = []
    for line in text.split("\n"):
        paragraphs.append(
            "<a:p><a:r><a:rPr lang=\"en-US\" sz=\"%d\" dirty=\"0\"/>"
            "<a:t>%s</a:t></a:r><a:endParaRPr lang=\"en-US\" sz=\"%d\"/></a:p>"
            % (size, escape(line), size)
        )
    return (
        "<p:sp>"
        "<p:nvSpPr><p:cNvPr id=\"%d\" name=\"%s\"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>"
        "<p:spPr><a:xfrm><a:off x=\"%d\" y=\"%d\"/><a:ext cx=\"%d\" cy=\"%d\"/></a:xfrm>"
        "<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom></p:spPr>"
        "<p:txBody><a:bodyPr/><a:lstStyle/>%s</p:txBody>"
        "</p:sp>"
    ) % (shape_id, name, x, y, cx, cy, "".join(paragraphs))


def slide_xml(title, body):
    shapes = shape(2, "Title", 457200, 274320, 8229600, 1143000, title, 3200)
    shapes += shape(3, "Body", 457200, 1600200, 8229600, 4525963, "\n".join(body), 1800)
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<p:sld xmlns:a=\"%s\" xmlns:r=\"%s\" xmlns:p=\"%s\">"
        "<p:cSld><p:spTree>"
        "<p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
        "<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/>"
        "<a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
        "%s</p:spTree></p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        "</p:sld>"
    ) % (NS_A, NS_R, NS_P, shapes)


def relationships(pairs):
    items = []
    for rel_id, rel_type, target in pairs:
        items.append(
            "<Relationship Id=\"%s\" Type=\"%s\" Target=\"%s\"/>" % (rel_id, rel_type, target)
        )
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"%s\">%s</Relationships>"
    ) % (NS_REL, "".join(items))


THEME = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="%s" name="Office">
  <a:themeElements>
    <a:clrScheme name="Office">
      <a:dk1><a:sysClr val="windowText" lastClr="000000"/></a:dk1>
      <a:lt1><a:sysClr val="window" lastClr="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="1F4E79"/></a:dk2>
      <a:lt2><a:srgbClr val="E7E6E6"/></a:lt2>
      <a:accent1><a:srgbClr val="5B9BD5"/></a:accent1>
      <a:accent2><a:srgbClr val="ED7D31"/></a:accent2>
      <a:accent3><a:srgbClr val="A9D08E"/></a:accent3>
      <a:accent4><a:srgbClr val="FFC000"/></a:accent4>
      <a:accent5><a:srgbClr val="4472C4"/></a:accent5>
      <a:accent6><a:srgbClr val="70AD47"/></a:accent6>
      <a:hlink><a:srgbClr val="0563C1"/></a:hlink>
      <a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="Office">
      <a:majorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>
      <a:minorFont><a:latin typeface="Calibri"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="Office">
      <a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>
      <a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>
      <a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
      <a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
</a:theme>
""" % NS_A


def write_pptx(path, markdown):
    slides = slides_from_markdown(markdown)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    overrides = [
        ("/ppt/presentation.xml", "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"),
        ("/ppt/slideMasters/slideMaster1.xml", "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"),
        ("/ppt/slideLayouts/slideLayout1.xml", "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"),
        ("/ppt/theme/theme1.xml", "application/vnd.openxmlformats-officedocument.theme+xml"),
        ("/ppt/presProps.xml", "application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"),
        ("/ppt/viewProps.xml", "application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"),
        ("/ppt/tableStyles.xml", "application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"),
    ]
    for index in range(1, len(slides) + 1):
        overrides.append((
            "/ppt/slides/slide%d.xml" % index,
            "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
        ))
    content_types = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>",
        "<Types xmlns=\"%s\">" % NS_CT,
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>",
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>",
    ]
    for part, content in overrides:
        content_types.append("<Override PartName=\"%s\" ContentType=\"%s\"/>" % (part, content))
    content_types.append("</Types>")

    sld_id = []
    pres_rels = [(
        "rId1",
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster",
        "slideMasters/slideMaster1.xml",
    )]
    for index in range(1, len(slides) + 1):
        rid = "rId%d" % (index + 1)
        pres_rels.append((
            rid,
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
            "slides/slide%d.xml" % index,
        ))
        sld_id.append("<p:sldId id=\"%d\" r:id=\"%s\"/>" % (255 + index, rid))
    pres_rels.append((
        "rId%d" % (len(slides) + 2),
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps",
        "presProps.xml",
    ))
    pres_rels.append((
        "rId%d" % (len(slides) + 3),
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps",
        "viewProps.xml",
    ))
    pres_rels.append((
        "rId%d" % (len(slides) + 4),
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles",
        "tableStyles.xml",
    ))

    presentation = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<p:presentation xmlns:a=\"%s\" xmlns:r=\"%s\" xmlns:p=\"%s\" saveSubsetFonts=\"1\">"
        "<p:sldMasterIdLst><p:sldMasterId id=\"2147483648\" r:id=\"rId1\"/></p:sldMasterIdLst>"
        "<p:sldIdLst>%s</p:sldIdLst>"
        "<p:sldSz cx=\"9144000\" cy=\"6858000\" type=\"screen4x3\"/>"
        "<p:notesSz cx=\"6858000\" cy=\"9144000\"/>"
        "</p:presentation>"
    ) % (NS_A, NS_R, NS_P, "".join(sld_id))

    master = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<p:sldMaster xmlns:a=\"%s\" xmlns:r=\"%s\" xmlns:p=\"%s\">"
        "<p:cSld><p:spTree>"
        "<p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
        "<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/>"
        "<a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
        "</p:spTree></p:cSld>"
        "<p:clrMap bg1=\"lt1\" tx1=\"dk1\" bg2=\"lt2\" tx2=\"dk2\" accent1=\"accent1\" "
        "accent2=\"accent2\" accent3=\"accent3\" accent4=\"accent4\" accent5=\"accent5\" "
        "accent6=\"accent6\" hlink=\"hlink\" folHlink=\"folHlink\"/>"
        "<p:sldLayoutIdLst><p:sldLayoutId id=\"2147483649\" r:id=\"rId1\"/></p:sldLayoutIdLst>"
        "</p:sldMaster>"
    ) % (NS_A, NS_R, NS_P)
    layout = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<p:sldLayout xmlns:a=\"%s\" xmlns:r=\"%s\" xmlns:p=\"%s\" type=\"title\" preserve=\"1\">"
        "<p:cSld name=\"Title\"><p:spTree>"
        "<p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
        "<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/>"
        "<a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
        "</p:spTree></p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        "</p:sldLayout>"
    ) % (NS_A, NS_R, NS_P)

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "".join(content_types))
        archive.writestr("_rels/.rels", relationships([
            ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", "ppt/presentation.xml"),
        ]))
        archive.writestr("ppt/presentation.xml", presentation)
        archive.writestr("ppt/_rels/presentation.xml.rels", relationships(pres_rels))
        archive.writestr("ppt/slideMasters/slideMaster1.xml", master)
        archive.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", relationships([
            ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout", "../slideLayouts/slideLayout1.xml"),
            ("rId2", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme", "../theme/theme1.xml"),
        ]))
        archive.writestr("ppt/slideLayouts/slideLayout1.xml", layout)
        archive.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", relationships([
            ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster", "../slideMasters/slideMaster1.xml"),
        ]))
        archive.writestr("ppt/theme/theme1.xml", THEME)
        archive.writestr("ppt/presProps.xml", "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><p:presentationPr xmlns:p=\"%s\"/>" % NS_P)
        archive.writestr("ppt/viewProps.xml", "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><p:viewPr xmlns:p=\"%s\"><p:normalViewPr><p:restoredLeft sz=\"15620\"/><p:restoredTop sz=\"94660\"/></p:normalViewPr><p:slideViewPr><p:cSldViewPr/></p:slideViewPr></p:viewPr>" % NS_P)
        archive.writestr("ppt/tableStyles.xml", "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><a:tblStyleLst xmlns:a=\"%s\" def=\"{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}\"/>" % NS_A)
        for index, (title, body) in enumerate(slides, start=1):
            archive.writestr("ppt/slides/slide%d.xml" % index, slide_xml(title, body))
            archive.writestr("ppt/slides/_rels/slide%d.xml.rels" % index, relationships([
                ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout", "../slideLayouts/slideLayout1.xml"),
            ]))
    return len(slides)


def read_text(path):
    lines = []
    with zipfile.ZipFile(path) as archive:
        names = sorted(
            name for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )
        for name in names:
            root = ET.fromstring(archive.read(name))
            texts = [node.text or "" for node in root.iter("{%s}t" % NS_A)]
            lines.append("\n".join(texts))
    return "\n\n".join(lines)


def self_test():
    sample = "# Launch\n\nShips Friday.\n\n# Risks\n\n- Supply\n"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "deck.pptx"
        count = write_pptx(out, sample)
        if count != 2:
            raise SystemExit("expected 2 slides, got %s" % count)
        text = read_text(out)
        if "Launch" not in text or "Supply" not in text or "Risks" not in text:
            raise SystemExit(text)
        with zipfile.ZipFile(out) as archive:
            for name in archive.namelist():
                if name.endswith(".xml"):
                    ET.fromstring(archive.read(name))
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
    text.add_argument("pptx")
    args = parser.parse_args(argv)
    if args.command == "create":
        count = write_pptx(args.out, Path(args.input).read_text(encoding="utf-8"))
        print("wrote %s (%d slides)" % (args.out, count))
    else:
        sys.stdout.write(read_text(args.pptx))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
