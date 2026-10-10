#!/usr/bin/env python3
"""Inject macdeployqt into macos_package target to fix framework rpaths."""
from pathlib import Path
import argparse
import sys

REL = Path('CMakeLists.txt')


def patch(text: str) -> str:
    if 'Qt6_MACDEPLOYQT_EXECUTABLE' in text:
        raise RuntimeError('macdeployqt injection already present')
    anchor = '''    add_custom_target(macos_package
        COMMAND "${CMAKE_COMMAND}" -E rm -rf
                "${CMAKE_INSTALL_PREFIX}/${ALCEDO_MACOS_BUNDLE_NAME}.app"
        COMMAND "${CMAKE_COMMAND}" --install "${CMAKE_BINARY_DIR}"
                --component "${ALCEDO_PACKAGE_INSTALL_COMPONENT}"
        COMMAND "${CMAKE_SOURCE_DIR}/scripts/verify_macos_install_tree.sh"
                --install-dir "${CMAKE_INSTALL_PREFIX}"
                --bundle-name "${ALCEDO_MACOS_BUNDLE_NAME}"
        COMMAND "${CMAKE_CPACK_COMMAND}" --config "${CMAKE_BINARY_DIR}/CPackConfig.cmake" -B "${CMAKE_INSTALL_PREFIX}"'''
    if text.count(anchor) != 1:
        raise RuntimeError('macos_package target anchor changed')
    # Insert macdeployqt after install, before verify
    new = anchor.replace(
        '        COMMAND "${CMAKE_SOURCE_DIR}/scripts/verify_macos_install_tree.sh"',
        '''        COMMAND "${CMAKE_COMMAND}" --install "${CMAKE_BINARY_DIR}"
                --component "${ALCEDO_PACKAGE_INSTALL_COMPONENT}"
        COMMAND "${Qt6_MACDEPLOYQT_EXECUTABLE}" "${CMAKE_INSTALL_PREFIX}/${ALCEDO_MACOS_BUNDLE_NAME}.app"
                -verbose=2 -always-overwrite -no-strip -codesign=-
        COMMAND "${CMAKE_SOURCE_DIR}/scripts/verify_macos_install_tree.sh"''')
    text = text.replace(anchor, new, 1)
    # Need to find Qt6_MACDEPLOYQT_EXECUTABLE - add find_program before the target
    find_anchor = 'include(CPack)'
    find_new = '''include(CPack)

# macdeployqt to fix framework rpaths and bundle all Qt dependencies
find_program(Qt6_MACDEPLOYQT_EXECUTABLE macdeployqt
    PATHS "${Qt6_DIR}/../bin" "${CMAKE_PREFIX_PATH}/bin"
    NO_DEFAULT_PATH
)
if(NOT Qt6_MACDEPLOYQT_EXECUTABLE)
    find_program(Qt6_MACDEPLOYQT_EXECUTABLE macdeployqt)
endif()
if(NOT Qt6_MACDEPLOYQT_EXECUTABLE)
    message(WARNING "macdeployqt not found - macOS bundle may have unresolved framework dependencies")
endif()'''
    if text.count(find_anchor) != 1:
        raise RuntimeError('include(CPack) anchor changed')
    text = text.replace(find_anchor, find_new, 1)
    return text


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
    print(f'{"Patch validation passed" if args.check else "Injected macdeployqt into macos_package"}: {target}')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError) as e:
        print(f'Patch failed: {e}', file=sys.stderr)
        sys.exit(1)