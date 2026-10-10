# Alcedo Studio — Intel macOS Port & Reusable Metal Build

**Status: build infrastructure and native Intel packaging port. The Metal shaders and full native app have NOT been compiled or GPU-tested in this Linux-based preparation environment.** A first successful GitHub Actions run and a physical Intel Mac test are still required before calling it functional.

This repository is an **overlay/launcher** for the upstream [Alcedo Studio](https://github.com/zidage/AlcedoStudio) source (GPL-3.0-only). The app remains an actual Qt/C++ native macOS app, **not a WebView**. The ZIP does not contain, repackage, or replace the entire upstream source repository. Workflows clone and pin it, then install a verified CMake extension.

## What this solves

1. GitHub's `macos-15-intel` runner compiles **all 17 upstream `.metal` sources** into a reusable `.metallib` collection **once**.
2. The collection is published as a persistent GitHub **Release asset** (`alcedo-intel-metal.zip`), not just a 30-day Actions artifact.
3. Subsequent x86_64 application builds **reuse those shaders** and do not call `xcrun metal` or `xcrun metallib`.
4. You may also compile the app **locally without installing full Xcode**, as long as you have macOS Command Line Tools, CMake, Qt, the rest of Alcedo's Homebrew libraries, and this shader package.
5. The manifest records SHA-256 hashes of every compiled Metal library and its compiler-discovered/explicit source dependencies. If a shader or dependent header changes, the app build **fails with a useful error** instead of silently using an incompatible library.

**Changes to C++/QML/UI code alone do not require recompiling shaders. Changes to `.metal` files or included shader math headers do.** The GPU can still compile compute pipeline states for its particular hardware at runtime; a portable `.metallib` is not guaranteed to precompile every Intel/AMD GPU-specific pipeline state.

## Requirements / limits

- **Intel Mac (x86_64), macOS 13.3 or newer**, with a functioning Metal-capable GPU. A Mac stuck on Catalina 10.15 cannot run current Alcedo Studio without a separate OS compatibility port.
- `macos-15-intel` is the GitHub Actions runner for source-to-binary builds; a macOS runner provides Xcode, even if your personal Mac does not have it.
- Metal runtime behavior, neural demosaicing (`MPSGraph`), color-parity, raw decode, UI launch, and export need testing on a real Intel GPU. GitHub-hosted macOS runners may lack usable graphics acceleration.
- GPU/model-dependent neural operations may require adaptation/fallback on Intel hardware. This patch does **not** claim to fix all such runtime issues.
- The local build still needs **Apple Command Line Tools** (`xcode-select --install`) for C++/Objective-C++ and native Qt dependencies. The cached shaders remove the *Metal shader compiler* requirement, not the normal C++ toolchain.
- The unsigned/ad-hoc-signed app will not be notarized. No Apple Developer account required for local use, but macOS Gatekeeper may prompt.
- The Rust semantic sidecar (`alcedo_mind`, AI image analysis / semantic search) is excluded from Intel builds: its ONNX Runtime dependency has no macOS x86_64 binaries (Microsoft dropped them after ORT 1.23). The core app (RAW pipeline, Metal GPU, export, albums) is complete; semantic AI features are absent and packaging checks are patched to skip them.

## Set up a dedicated GitHub repository

1. Create a **new public GitHub repository**, e.g. `AlcedoStudio-Intel`. (Don't modify SpektraFilm.)
2. Extract this ZIP and commit all files **including the hidden `.github/workflows` folder**:

   ```bash
   cd AlcedoStudio-Intel-Port
   git init
   git add -A
   git commit -m 'Intel Metal cache and native app build'
   git branch -M main
   git remote add origin https://github.com/YOUR-ACCOUNT/AlcedoStudio-Intel.git
   git push -u origin main
   ```
3. Under **GitHub → Actions**, select **01 - Compile Intel Metal once** and **Run workflow**. Keep the default pinned upstream revision for the first pass.
4. A successful run creates a Release `intel-metal-...` containing `alcedo-intel-metal.zip`, plus a temporary Actions artifact.
5. Select **02 - Build native Intel app (reuse Metal)** and **Run workflow**. It downloads the published `.metallib` bundle, builds Alcedo for `x86_64`, and uploads `AlcedoStudio-Intel-x86_64.zip` as a workflow artifact.
6. Open the app artifact on your Mac. **This is an experimental port**, so test with a small RAW image first; then check editing, LUTs, RCD/Bayer demosaic, X-Trans neural demosaic, and export.

Neither workflow needs Xcode on your computer. The first workflow runs only when you explicitly select it. The second one reuses the Metal release and refuses outdated shader inputs. GitHub Actions usage may incur charges for private repositories; check your plan before running resource-heavy jobs.

### Use your own fork of Alcedo

Both workflows accept `source_repository` (`owner/name`) and `upstream_ref` (commit/tag). Set them to your Alcedo fork and its revision if you make your own C++/QML changes. If those changes don't touch Metal shader inputs, **reuse the same Metal Release**. If they do, rerun workflow 01 first. For a reproducible build, prefer a fixed commit SHA over a moving `main` branch.

## Build on your Intel Mac **without full Xcode**

1. Install the Apple Command Line Tools: `xcode-select --install`.
2. Install dependencies; see [upstream build instructions](https://github.com/zidage/AlcedoStudio/blob/main/docs/build_from_source.md):

   ```bash
   brew install cmake ninja qt opencv opencolorio duckdb exiv2 glib libraw little-cms2 highway openimageio pkg-config xxhash eigen libomp libarchive grpc protobuf openblas
   ```
3. In this repository directory, prepare the source:

   ```bash
   bash scripts/intel_port/bootstrap_local.sh
   ```
4. Download the **published** `alcedo-intel-metal.zip` from your repo's GitHub **Releases** and place it in this directory, then run:

   ```bash
   python3 scripts/intel_port/metal_cache.py extract --archive alcedo-intel-metal.zip --out precompiled-metal
   python3 scripts/intel_port/metal_cache.py verify --root upstream --cache precompiled-metal
   bash scripts/intel_port/build_local.sh
   ```

This can rebuild and iterate on the C++ and QML source on the same Intel Mac without uploading every change to GitHub. If a `.metal` file changes, you must create a new shader Release with workflow 01 and download it again. `build_local.sh` builds an app bundle, but advanced packaging/dependency collection may still require an additional `macdeployqt` step.

### Check your Intel Mac's Metal support

Run:

```bash
bash tests/gpu/check_intel_metal.sh
```

It compiles a tiny native Objective-C++ Metal probe using Apple's Command Line Tools, displays the detected GPU, and rejects macOS below 13.3 or Macs without a Metal GPU.

## Implementation layout

| Path | Purpose |
| --- | --- |
| `.github/workflows/01-compile-intel-metal-once.yml` | Build and permanently publish Metal libraries |
| `.github/workflows/02-build-native-intel-app.yml` | Build native macOS Intel application using cached libraries |
| `scripts/intel_port/apply_port.py` | Modify upstream Metal CMake dependency definitions only |
| `scripts/intel_port/metal_cache.py` | Compile, extract, SHA-256 validate shaders and dependencies |
| `scripts/intel_port/bootstrap_local.sh` | Clone/pin Alcedo and apply integration locally |
| `scripts/intel_port/build_local.sh` | Native app build, no local Metal toolchain |
| `tests/gpu/` | Small native Intel GPU / Metal eligibility probe |
| `tests/test_port.py` | Portable unit tests for patch and manifest behavior |

Run portable tests with `python3 -m unittest discover -s tests -v`.

### Technical notes

- Alcedo already installs `.metallib` files into its app at `Contents/Resources/metallib/` and loads via its `ComputePipelineCache` from the bundle. We use that mechanism unchanged.
- The integrated CMake option is `-DALCEDO_PREBUILT_METAL_DIR=/absolute/path/to/precompiled-metal`. Configure-time SHA checking prevents mixing revised shader sources and old outputs.
- The original shader builder remains available if the option is empty; the CMake extension does not delete or replace it.
- The regular native application still needs normal C++ linking, Qt packaging, submodules, and third-party libraries. There is no practical guarantee that every upstream change will be buildable without other work.
- The original Alcedo Studio source is **GPL-3.0-only**. Retain copyright, notices, corresponding source, and third-party licenses when distributing derivative binaries. See [upstream LICENSE](https://github.com/zidage/AlcedoStudio/blob/main/LICENSE) and [third-party notices](https://github.com/zidage/AlcedoStudio/blob/main/THIRD_PARTY_NOTICE.txt).

### Provenance

- Inspected upstream: `zidage/AlcedoStudio`, commit `d20a14b0c5bc54fac50b163173cb352bfe24be0f` (2026-10-10 checked tree).
- Verified upstream currently has 17 named Metal library targets in `alcedo_studio/src/metal/CMakeLists.txt`.
- Native app compilation and GPU smoke tests could not be performed on this Linux development host.
