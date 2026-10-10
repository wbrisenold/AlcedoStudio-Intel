#!/usr/bin/env python3
"""Build/verify reusable Alcedo Metal libraries. Python stdlib only.

GPL-3.0-only derivative integration; see upstream NOTICE and LICENSE.
This script does NOT silently accept old metallibs after a shader/header change.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import zipfile

METAL_CMAKE = Path('alcedo_studio/src/metal/CMakeLists.txt')
MANIFEST = 'alcedo-metal-manifest.json'
FORMAT = 1


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def repo_rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def sources(root: Path) -> dict[str, Path]:
    cmake = (root / METAL_CMAKE).read_text()
    mapping = {}
    expr = r'set\(\s*(METAL_[A-Z0-9_]+)_SRC\s+"\$\{ALCEDO_SRC_ROOT\}/([^"\)]+)"\s*\)'
    for m in re.finditer(expr, cmake):
        file = root / 'alcedo_studio/src' / m.group(2)
        if not file.is_file() or file.suffix != '.metal':
            raise ValueError(f'Missing upstream Metal source: {file}')
        name = file.stem + '.metallib'
        if name in mapping:
            raise ValueError(f'Non-unique Metal library name: {name}')
        mapping[name] = file
    if len(mapping) < 16:
        raise ValueError(f'Expected at least 16 named upstream Metal libraries; found {len(mapping)}. Upstream layout changed?')
    return dict(sorted(mapping.items()))


def explicit_deps(root: Path, shader: Path) -> set[Path]:
    """Extract explicit DEPENDS from the matching CMake library invocation."""
    cmake = (root / METAL_CMAKE).read_text()
    variable = re.search(r'set\(\s*(METAL_[A-Z0-9_]+)_SRC\s+"\$\{ALCEDO_SRC_ROOT\}/' + re.escape(repo_rel(root / 'alcedo_studio/src', shader)) + r'"\s*\)', cmake)
    if not variable:
        return set()
    src_var = variable.group(1) + "_SRC"
    blocks = re.findall(r'alcedo_add_metal_library\(\s*[^\n]+.*?\n\s*\)', cmake, re.S)
    matched = [b for b in blocks if '${' + src_var + '}' in b]
    if len(matched) != 1:
        raise ValueError(f'Cannot resolve unique shader invocation: {src_var}')
    block = matched[0]
    out = set()
    # Only the trailing DEPENDS portion is a declared source dependency.
    if 'DEPENDS' in block:
        trailing = block.split('DEPENDS', 1)[1].split('COMPILE_FLAGS', 1)[0]
        for kind, rel in re.findall(r'"\$\{(ALCEDO_(?:SRC|INCLUDE)_ROOT)\}/([^"\)]+)"', trailing):
            parent = 'alcedo_studio/src' if kind == 'ALCEDO_SRC_ROOT' else 'alcedo_studio/src/include'
            dep = root / parent / rel
            if not dep.is_file():
                raise ValueError(f'Missing shader explicit dependency: {dep}')
            out.add(dep)
    return out


def compile_library(root: Path, out: Path, name: str, shader: Path, deployment: str, depdir: Path) -> dict:
    depfile = depdir / (name + '.d')
    air = depdir / (name + '.air')
    output = out / name
    command = ['xcrun', '--sdk', 'macosx', 'metal', '-MMD', '-fno-color-diagnostics',
               f'-mmacosx-version-min={deployment}', '-O3',
               f'-fmodules-cache-path={depdir / "module-cache"}', '-MF', str(depfile)]
    if name == 'display_to_ap1.metallib':
        # Required upstream: inverse ACES branch is tested without fast math.
        command.append('-fno-fast-math')
    command += ['-c', str(shader), '-o', str(air)]
    print(f'Compiling {name}', flush=True)
    subprocess.run(command, check=True, cwd=root)
    subprocess.run(['xcrun', '--sdk', 'macosx', 'metallib', str(air), '-o', str(output)], check=True, cwd=root)
    if not output.is_file() or output.stat().st_size < 64:
        raise RuntimeError(f'Metal compilation did not produce a valid output: {output}')
    deps = {shader, *explicit_deps(root, shader)}
    if depfile.exists():
        raw = depfile.read_text()
        # Strip makefile line continuations and split after the first unescaped colon.
        raw = raw.replace('\\\n', ' ')
        match = re.search(r'(?<!\\):\s*', raw)
        if match:
            for item in shlex.split(raw[match.end():]):
                p = Path(item)
                if not p.is_absolute():
                    p = root / p
                try:
                    p.resolve().relative_to(root.resolve())
                except ValueError:
                    continue
                if p.is_file():
                    deps.add(p)
    return {'file': name, 'sha256': sha256(output), 'bytes': output.stat().st_size,
            'inputs': {repo_rel(root, p): sha256(p) for p in sorted(deps)}}


def compile_all(root: Path, output: Path, deployment: str, archive: Path | None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='alcedo-metal-') as work:
        tmp = Path(work)
        (tmp / 'module-cache').mkdir()
        entries = [compile_library(root, output, name, file, deployment, tmp)
                   for name, file in sources(root).items()]
    info = {'schema': FORMAT, 'project': 'Alcedo Studio — Intel Metal cache',
            'source_repository': subprocess.check_output(['git', 'remote', 'get-url', 'origin'], cwd=root, text=True).strip(),
            'platform': 'macos', 'deployment_target': deployment,
            'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(), 'libraries': entries}
    (output / MANIFEST).write_text(json.dumps(info, indent=2, sort_keys=True) + '\n')
    verify(root, output)
    if archive:
        archive.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for item in sorted(output.iterdir()):
                if item.is_file():
                    z.write(item, item.name)
        print(f'Archived reusable Metal package: {archive}', flush=True)


def verify(root: Path, cache: Path) -> None:
    metadata_path = cache / MANIFEST
    if not metadata_path.is_file():
        raise ValueError(f'Missing {MANIFEST} in {cache}')
    data = json.loads(metadata_path.read_text())
    if data.get('schema') != FORMAT or data.get('platform') != 'macos':
        raise ValueError('Unsupported Metal manifest / target platform')
    if data.get('deployment_target') != '13.3':
        raise ValueError('Expected a macOS 13.3-compatible Metal library package')
    current = sources(root)
    built = {x['file']: x for x in data['libraries']}
    if set(built) != set(current):
        raise ValueError(f'Metal library set changed: added {sorted(set(current)-set(built))}, removed {sorted(set(built)-set(current))}')
    for name, shader in current.items():
        record = built[name]
        library = cache / name
        if not library.is_file() or sha256(library) != record['sha256']:
            raise ValueError(f'Compiled library missing/tampered: {name}')
        inputs = record['inputs']
        required = {repo_rel(root, shader)} | {repo_rel(root, d) for d in explicit_deps(root, shader)}
        if not required.issubset(inputs.keys()):
            raise ValueError(f'Incomplete shader dependency record: {name}')
        for relative, expected in inputs.items():
            p = (root / relative).resolve()
            if not p.is_relative_to(root.resolve()) or not p.is_file() or sha256(p) != expected:
                raise ValueError(f'Shader input changed; recompile Metal: {name}: {relative}')
    print(f'Verified {len(current)} Metal libraries against current shader sources and dependencies.', flush=True)


def extract(archive: Path, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if name != MANIFEST and not re.fullmatch(r'[A-Za-z_0-9.-]+\.metallib', name):
                raise ValueError(f'Unexpected archive member: {name}')
        z.extractall(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    make = sub.add_parser('compile')
    make.add_argument('--root', type=Path, default=Path('.'))
    make.add_argument('--out', type=Path, required=True)
    make.add_argument('--archive', type=Path)
    make.add_argument('--deployment', default='13.3')
    test = sub.add_parser('verify')
    test.add_argument('--root', type=Path, default=Path('.'))
    test.add_argument('--cache', type=Path, required=True)
    unpack = sub.add_parser('extract')
    unpack.add_argument('--archive', type=Path, required=True)
    unpack.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'compile':
        if args.deployment != '13.3':
            parser.error('Intel reusable shader package currently targets macOS 13.3')
        compile_all(args.root.resolve(), args.out.resolve(), args.deployment, args.archive.resolve() if args.archive else None)
    if args.command == 'verify':
        verify(args.root.resolve(), args.cache.resolve())
    if args.command == 'extract':
        extract(args.archive, args.out)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, subprocess.CalledProcessError, OSError) as e:
        print(f'Intel Metal cache error: {e}', file=sys.stderr)
        sys.exit(1)
