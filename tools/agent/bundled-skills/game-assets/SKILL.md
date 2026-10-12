---
name: game-assets
description: Build engine-ready game files with scripts/make_asset.py. SVG icons, sprite sheets, tilesets, PPM images, and a GLB box mesh. Use for sprites, tilesets, HUD icons, or a mesh. No image service is called.
license: MIT
compatibility: python3
allowed-tools: bash read write edit glob
---

# Game files

Generate the file with `<skill_dir>/scripts/make_asset.py`. `<skill_dir>` is the directory that contains this file. Ask for the pixel size when the user did not give one. Defaults are 64 for an icon, 32 for a tile or frame, and 4 frames for a cycle.

```bash
python3 <skill_dir>/scripts/make_asset.py icon --out icon.svg --label S --size 64
python3 <skill_dir>/scripts/make_asset.py sheet --out walk.svg --frames 4 --size 32
python3 <skill_dir>/scripts/make_asset.py tileset --out tiles.svg --cols 4 --rows 4 --tile 32
python3 <skill_dir>/scripts/make_asset.py ppm --out tile.ppm --size 16
python3 <skill_dir>/scripts/make_asset.py glb --out box.glb
```

Read the file back before you finish.

- An SVG icon is square, has the requested label, and states its width and height.
- A sheet is one horizontal row. Frames are the same size and are not identical. The script prints `frames=` and `frame=`.
- A tileset is a grid of `cols` by `rows` cells. Adjacent cells use different fills.
- A PPM is a binary `P6` image of the requested size.
- A GLB is a unit cube centered on the origin, y-up, with 12 triangles. Mount it with the threejs-frame-conventions skill when the engine is y-up.

Name files for the engine (`walk_01`, `tile_grass`). Report width, height, frame count, and path. These files are drawn by the script. Do not describe art the file does not contain.
