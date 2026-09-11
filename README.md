# RE4R Character Replacer Generator

A Windows desktop tool for building **Resident Evil 4 (2023) character replacement mods** from user-supplied models. This repository contains the generator itself, not a character skin or extracted game content.

The current preview supports automatic runtime-path discovery with manual overrides, local browser UI with an adaptive port, native model/folder selection, reference-resource extraction, Blender-assisted pose alignment, material/texture conversion, and Fluffy Mod Manager-ready packaging.

> [!IMPORTANT]
> This is preview software. Keep backups and inspect generated mods before distributing them. You must own the game and provide your own model files. No game assets or third-party character models are included here.

## 0.4.4 preview fixes

- Blender 5.2-compatible helper material creation; node lookup no longer depends on localized display names.
- Recursive Base Color graph inspection, including nested node groups.
- Better base-color texture selection for C/CSAR/MRA/N texture sets.
- Safe recovery of moved texture files by unique filename match.
- Self-contained PAK helper packaging, including the native `libzstd.dll` dependency.
- Correct handling of patch PAKs that contain zero requested files.
- Adaptive local port selection and a native, user-friendly model/folder picker.

## End-user prerequisites

- Windows 10 or 11, 64-bit
- Resident Evil 4 (2023), Steam version
- Blender 4.2 through 5.2; Blender 5.2 is covered by the compatibility tests in this revision
- Fluffy Mod Manager for installing the generated mod

For end-user setup and usage, see [RELEASE_README.md](RELEASE_README.md).

## Build from source

Install Git, Python 3.11 or newer, the .NET 10 SDK, and a supported Blender version.

```powershell
git clone --recursive https://github.com/PaiPai121/RE4R-Character-Replacer-Generator.git
cd RE4R-Character-Replacer-Generator
powershell -ExecutionPolicy Bypass -File .\tools\Package-Replacer.ps1
```

The package and its SHA-256 manifest are written to `release/`.

This project uses pinned Git submodules for RE Mesh Editor, MMD Tools, and the PAK-format build dependency. If you cloned without `--recursive`, run:

```powershell
git submodule update --init --recursive
```

## Tests

Run the application tests:

```powershell
python -m pip install -r requirements-dev.txt
cd replacer_app
python -m unittest test_adjust_endpoint test_dds_fallback test_fluffy_package test_game_resources test_model_directory test_pipeline test_runtime_paths test_static_server
```

Build the native components:

```powershell
dotnet build .\tools\replacer_launcher\ReplacerLauncher.csproj -c Release
dotnet build .\tools\replacer_pak\ReplacerPak.csproj -c Release
```

Blender compatibility checks are intended to run through Blender's Python runtime:

```powershell
blender --background --factory-startup --python .\scripts\test_blender_52_materials.py
blender --background --factory-startup --python .\scripts\test_blender_52_full_build.py -- <SOURCE_INPUT.blend> <SOURCE_REQUEST.json> .\work\blender52-full-build
```

The full-build test uses a locally supplied test model and reference assets; those files are deliberately excluded from the repository.

## Data and redistribution policy

- Do not commit extracted PAK contents, `.mesh`, `.mdf2`, `.tex`, model files, generated `.blend` files, or user project records.
- Only use and redistribute source models when their licenses permit it.
- Resident Evil, RE ENGINE, and related names and assets belong to their respective owners.
- This project is not affiliated with or endorsed by Capcom.

## License

Original generator code is licensed under GPL-3.0-or-later. See [LICENSE](LICENSE) and [LICENSE-NOTICE.md](LICENSE-NOTICE.md). Third-party components remain under their own terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
