#!/usr/bin/env bash
# Build native Alcedo Studio on an Intel Mac with no installed full Xcode.
# Requires Apple Command Line Tools, native dependencies and a downloaded Metal cache.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source_dir="${ALCEDO_SOURCE_DIR:-$here/upstream}"
cache_dir="${ALCEDO_METAL_CACHE_DIR:-$here/precompiled-metal}"
[[ "$(uname -s)" == Darwin ]] || { echo 'This script requires macOS'; exit 1; }
[[ "$(uname -m)" == x86_64 ]] || { echo 'This local builder targets Intel x86_64 Macs'; exit 1; }
command -v cmake >/dev/null || { echo 'Install cmake and ninja using Homebrew first'; exit 1; }
command -v brew >/dev/null || { echo 'Homebrew is required for native dependencies'; exit 1; }
if [[ ! -d "$source_dir" ]]; then
  bash "$here/scripts/intel_port/bootstrap_local.sh" "$source_dir"
fi
if [[ ! -f "$cache_dir/alcedo-metal-manifest.json" ]]; then
  echo "No precompiled Metal package in $cache_dir"
  echo 'Download alcedo-intel-metal.zip from workflow 01 GitHub Release into the port folder, then run:'
  echo "  python3 scripts/intel_port/metal_cache.py extract --archive alcedo-intel-metal.zip --out precompiled-metal"
  exit 2
fi
python3 "$here/scripts/intel_port/metal_cache.py" verify --root "$source_dir" --cache "$cache_dir"
qt_root="$(brew --prefix qt)"
cmake -S "$source_dir" -B "$source_dir/build/intel-local" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_OSX_ARCHITECTURES=x86_64 \
    -DCMAKE_OSX_DEPLOYMENT_TARGET=13.3 \
    -DALCEDO_METAL_SHADER_DEPLOYMENT_TARGET=13.3 \
    -DALCEDO_PREBUILT_METAL_DIR="$cache_dir" \
    -DALCEDO_ENABLE_METAL=ON -DALCEDO_ENABLE_CUDA=OFF \
    -DALCEDO_ENABLE_WEBGPU=OFF -DALCEDO_MACOS_BUNDLE=ON \
    -DALCEDO_BUILD_TESTS=OFF -DALCEDO_REQUIRE_UPDATE_KEY=OFF \
    -DPUERHLAB_USE_BUNDLED_LIBRAW=ON \
    -DPUERHLAB_USE_SYSTEM_GRPC_PROTOBUF=ON \
    -DALCEDO_QT_PREFIX="$qt_root" \
    -DCMAKE_PREFIX_PATH="$qt_root"
cmake --build "$source_dir/build/intel-local" --target alcedo_main --parallel 4
find "$source_dir/build/intel-local" -type d -name 'AlcedoStudio.app' -print
