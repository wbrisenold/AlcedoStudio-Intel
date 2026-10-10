#!/usr/bin/env bash
# Set up upstream Alcedo Studio with the Intel + cached Metal adaptation.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ref="${ALCEDO_UPSTREAM_REF:-d20a14b0c5bc54fac50b163173cb352bfe24be0f}"
dest="${1:-$here/upstream}"
if [[ ! -d "$dest/.git" ]]; then
  git clone https://github.com/zidage/AlcedoStudio.git "$dest"
fi
git -C "$dest" fetch origin "$ref" || :
git -C "$dest" checkout "$ref"
# lensfun/metal-cpp have no gitlinks upstream; this script clones everything needed.
bash "$dest/scripts/ci_prepare_third_party.sh"
mkdir -p "$dest/scripts/intel_port"
cp "$here/scripts/intel_port/metal_cache.py" "$here/scripts/intel_port/apply_port.py" "$here/scripts/intel_port/patch_verify_sidecar.py" "$dest/scripts/intel_port/"
if ! grep -q 'ALCEDO_PREBUILT_METAL_DIR' "$dest/alcedo_studio/src/metal/CMakeLists.txt"; then
  python3 "$here/scripts/intel_port/apply_port.py" --root "$dest"
else
  echo 'Existing Intel integration detected. No double patch.'
fi
if ! grep -q 'Intel port builds without the semantic sidecar' "$dest/scripts/verify_macos_install_tree.sh"; then
  python3 "$here/scripts/intel_port/patch_verify_sidecar.py" --root "$dest"
else
  echo 'Existing sidecar-skip packaging checks detected. No double patch.'
fi
printf 'Intel source directory: %s\n' "$dest"
