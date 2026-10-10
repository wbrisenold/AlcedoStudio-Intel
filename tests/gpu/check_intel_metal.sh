#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ "$(uname -s)" == Darwin && "$(uname -m)" == x86_64 ]] || { echo 'Intel macOS required'; exit 1; }
clang++ -std=c++17 -arch x86_64 -fobjc-arc -framework Foundation -framework Metal \
  "$here/metal_probe.mm" -o "${TMPDIR:-/tmp}/alcedo-intel-metal-probe"
"${TMPDIR:-/tmp}/alcedo-intel-metal-probe"
