---
name: pdf
description: Create, read, and merge PDF files with scripts/pdf_tool.py. Use whenever the task has a .pdf as input or output. qpdf and pdftotext are used only when they are already installed.
license: MIT
compatibility: python3. Optional qpdf and pdftotext.
allowed-tools: bash read write edit glob
---

# PDF

Use `<skill_dir>/scripts/pdf_tool.py`. `<skill_dir>` is the directory that contains this file.

```bash
python3 <skill_dir>/scripts/pdf_tool.py create --out output.pdf --input notes.txt
python3 <skill_dir>/scripts/pdf_tool.py text input.pdf
python3 <skill_dir>/scripts/pdf_tool.py merge --out combined.pdf a.pdf b.pdf
```

`create` writes Helvetica text pages, wrapped to the page width. `text` uses `pdftotext` when it is on `PATH`, and otherwise reads the text operators in the file. `merge` uses `qpdf` when it is installed. Without `qpdf` it extracts the text of each input and writes one new PDF.

Read the extracted text after you write a file and confirm the user's words are there. If extraction of a scanned PDF is empty, say that the page has no text layer. Do not invent page contents. Do not promise encryption, form filling, or OCR. Those need tools this script does not include.
