#!/usr/bin/env python3
"""Skip semantic-sidecar packaging checks when the sidecar is absent (Intel port)."""
from pathlib import Path
import argparse
import sys

REL = Path('scripts/verify_macos_install_tree.sh')


def patch(text: str) -> str:
    if 'Intel port builds without the semantic sidecar' in text:
        raise RuntimeError('Sidecar skip already applied. Refusing to patch twice.')
    old = 'assert_executable "$mind_exe"\n'
    new = '''if [[ -x "$mind_exe" ]]; then
  assert_executable "$mind_exe"
else
  echo "note: Intel port builds without the semantic sidecar; skipping sidecar checks"
fi
'''
    if text.count(old) != 1:
        raise RuntimeError('Upstream verify mind assert anchor changed')
    text = text.replace(old, new, 1)
    # Sidecar prompts are installed only by the gated sidecar copy step.
    old = '  "${macos_dir}/configs/prompts/image_analysis_system_prompts.json"\n'
    if text.count(old) != 1:
        raise RuntimeError('Upstream verify prompts anchor changed')
    text = text.replace(old, '', 1)
    old = '''for file in "${required_files[@]}"; do
  assert_file "$file"
done
'''
    new = '''for file in "${required_files[@]}"; do
  assert_file "$file"
done

# Intel port: sidecar prompts ship only with the sidecar runtime.
if [[ -x "$mind_exe" ]]; then
  assert_file "${macos_dir}/configs/prompts/image_analysis_system_prompts.json"
fi
'''
    if text.count(old) != 1:
        raise RuntimeError('Upstream verify required-files loop anchor changed')
    text = text.replace(old, new, 1)
    old = '''if ! otool -L "$mind_exe" | grep -q '/System/Library/Frameworks/CoreML.framework/'; then
  fail "semantic sidecar is not linked against CoreML.framework: $mind_exe"
fi

if otool -L "$mind_exe" | grep -q '@rpath/libswift'; then
  if ! otool -l "$mind_exe" | grep -q 'path /usr/lib/swift (offset'; then
    fail "semantic sidecar has @rpath Swift dependencies but no /usr/lib/swift LC_RPATH"
  fi
fi
'''
    new = 'if [[ -x "$mind_exe" ]]; then\n' + old + 'fi\n'
    if text.count(old) != 1:
        raise RuntimeError('Upstream verify sidecar linkage anchors changed')
    return text.replace(old, new, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'), help='AlcedoStudio fork checkout')
    parser.add_argument('--check', action='store_true', help='Test the patch without writing')
    args = parser.parse_args()
    target = args.root / REL
    if not target.is_file():
        parser.error(f'Not an Alcedo Studio source checkout: missing {target}')
    old = target.read_text()
    new = patch(old)
    if not args.check:
        target.write_text(new)
    print(f'{"Patch validation passed" if args.check else "Installed Intel sidecar-skip packaging checks"}: {target}')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError) as e:
        print(f'Patch failed: {e}', file=sys.stderr)
        sys.exit(1)
