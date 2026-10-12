---
name: pptx
description: Create and read .pptx slide decks with scripts/pptx_tool.py. Use for slides, a pitch deck, a presentation, or any .pptx file. The script uses only the Python standard library.
license: MIT
compatibility: python3
allowed-tools: bash read write edit glob
---

# Slides

Use `<skill_dir>/scripts/pptx_tool.py`. `<skill_dir>` is the directory that contains this file.

Each slide starts with a `#` heading. The following non-empty lines are the body.

```markdown
# Title
One sentence.

# Second
- A point
```

```bash
python3 <skill_dir>/scripts/pptx_tool.py create --out deck.pptx --input slides.md
python3 <skill_dir>/scripts/pptx_tool.py text deck.pptx
```

To edit a deck, extract the text, change the Markdown, and write the file again. Confirm the extracted text contains every slide title. Keep one idea per slide. The script writes a title box and a body box. It does not place pictures or charts.
