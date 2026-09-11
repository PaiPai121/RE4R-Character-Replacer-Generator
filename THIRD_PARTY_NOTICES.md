# Third-party notices

The release contains source-form third-party Blender add-ons so users can inspect the exact code that runs locally.

## RE Mesh Editor

- Project: RE Mesh Editor by NSACloud
- Upstream: https://github.com/NSACloud/RE-Mesh-Editor
- Bundled revision: `622daa75b41ec622c3444ecb44ef31a651692687`
- License: GNU General Public License v3 (`tools/RE-Mesh-Editor/LICENSE.GPL`)

## MMD Tools

- Project: MMD Tools
- Upstream: https://github.com/MMD-Blender/blender_mmd_tools
- Bundled version: 4.5.11 source snapshot
- License: GNU General Public License v3 (`vendor/blender_mmd_tools/LICENSE`)

MMD Tools also contains an OpenCC data notice in its own source tree. Those files retain their original notices.

## Zstandard.Net

- Project: Zstandard.Net by bp74
- Upstream: https://github.com/bp74/Zstandard.Net
- Bundled binary version: 1.1.4
- License: BSD license as published by the upstream project

The binary is used by the local `ReplacerPak` helper for Zstandard-compressed PAK entries.

## REE.PAK.Tool

- Project: REE.PAK.Tool by Ekey
- Upstream: https://github.com/Ekey/REE.PAK.Tool
- Build-time revision: `3b14fcea96759b00adc734a3c563de74884dd798`
- License: the referenced upstream revision does not include a license file

Selected source files are compiled into the local `ReplacerPak` helper. This dependency remains in a separate Git submodule so its provenance and upstream terms are explicit; it is not covered by this repository's GPL license.

## Blender

Blender is an external prerequisite and is not bundled. See https://www.blender.org/ for downloads and licensing information.

## Game and mod-manager names

Resident Evil, RE ENGINE, and related names and assets belong to their respective owners. Fluffy Mod Manager is a separate third-party project and is not bundled.
