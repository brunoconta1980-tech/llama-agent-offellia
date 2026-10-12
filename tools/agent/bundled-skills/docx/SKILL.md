---
name: docx
description: Create and read Word .docx files with scripts/docx_tool.py. Use for a Word document, .docx, .dotx, headings, tables, or a letter. The script uses only the Python standard library.
license: MIT
compatibility: python3
allowed-tools: bash read write edit glob
---

# Word documents

Use `<skill_dir>/scripts/docx_tool.py`. `<skill_dir>` is the directory that contains this file. Do not require a Node package or an external editor.

Write the content as Markdown first, then build the docx.

- `#`, `##`, and `###` become headings.
- A blank line separates paragraphs.
- Lines starting with `- ` become list items.
- A GitHub-style table becomes a table. The separator row is skipped.

```bash
python3 <skill_dir>/scripts/docx_tool.py create --out output.docx --input content.md
python3 <skill_dir>/scripts/docx_tool.py text output.docx
```

To change an existing document, run `text`, edit the Markdown, and write a new docx. Read the extracted text back and confirm the headings and table cells the user asked for are present. Escape of `&` and `<` is handled by the script. Do not claim a feature the script does not write. It writes headings, paragraphs, lists, and tables.
