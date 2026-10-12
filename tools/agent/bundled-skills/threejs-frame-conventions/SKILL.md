---
name: threejs-frame-conventions
description: Keep Three.js and other y-up right-handed movement, camera, facing, and collision in one spatial frame. Use when editing controls, camera, character orientation, asset mounting, or collision. Run scripts/frame_check.py for the numeric sign checks.
license: MIT
compatibility: python3
allowed-tools: bash read write edit glob
---

# One frame

Movement, camera, facing, and collision must come from one source. A second `sin` or `cos` of the same yaw will disagree on a sign. Run this before you finish a change that touches those systems. `<skill_dir>` is the directory that contains this file.

```bash
python3 <skill_dir>/scripts/frame_check.py
```

The script checks three facts. Do not invert them in the game code.

- `forward (0,0,-1)` crossed with `up (0,1,0)` is `right (1,0,0)`. The other order is left.
- A mesh whose front is local -z uses `rotation.y = atan2(-direction.x, -direction.z)`. `lookAt` points +z at the target, so it faces a character the wrong way unless you add half a turn after measuring the asset front.
- A 2D angle `phi = atan2(z, x)` becomes `rotation.y = -phi` before it is copied onto a mesh or a collider.

## While editing

Read the camera direction every frame for camera-relative movement. Do not rebuild that basis from a second yaw variable.

```js
const fwd = new THREE.Vector3();
camera.getWorldDirection(fwd);
fwd.y = 0;
fwd.normalize();
const right = new THREE.Vector3().crossVectors(fwd, UP);
```

Place the camera from that same forward vector. Name vectors with their frame (`fwdWorld`, `dirCam`). Do not pass a shared scratch vector into a function that writes it.

Measure a loaded model's front from a marker or a bone pair. Store that vector once. Mount it onto local -z. The check that the mount matches the parent must use a different cue from the one that built the mount.

Give rendered meshes and colliders the same conversion helper. A collider without a mesh, or a mesh the player can touch without a collider, needs an explicit exception.

Search your edit for `Math.sin`, `Math.cos`, `lookAt`, `atan2`, `crossVectors`, and `rotation.y =`. Each hit is either the single owner of that frame or it should be deleted. If `frame_check.py` fails, fix the derivation it names.
