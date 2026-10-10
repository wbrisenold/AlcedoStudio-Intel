#!/usr/bin/env python3
"""Idempotent patch of upstream Metal CMake infrastructure for reusable libraries."""
from pathlib import Path
import argparse
import sys

REL = Path('alcedo_studio/src/metal/CMakeLists.txt')


def patch(text: str) -> str:
    if 'ALCEDO_PREBUILT_METAL_DIR' in text:
        raise RuntimeError('Prebuilt Metal integration already present. Refusing to patch twice.')
    anchor = 'if(ALCEDO_METAL_ENABLED)\n'
    if not text.startswith('# Metal target ownership') or text.count(anchor) != 1:
        raise RuntimeError('Upstream CMake structure changed; manual review required')
    prologue = '''if(ALCEDO_METAL_ENABLED)
    # Intel portability: reuse a verified Metal library pack produced once in CI.
    set(ALCEDO_PREBUILT_METAL_DIR "" CACHE PATH "Precompiled verified .metallib directory")
    if(ALCEDO_PREBUILT_METAL_DIR)
        if(NOT IS_DIRECTORY "${ALCEDO_PREBUILT_METAL_DIR}")
            message(FATAL_ERROR "Missing precompiled Metal directory: ${ALCEDO_PREBUILT_METAL_DIR}")
        endif()
        find_package(Python3 REQUIRED COMPONENTS Interpreter)
        execute_process(
            COMMAND "${Python3_EXECUTABLE}" "${CMAKE_SOURCE_DIR}/scripts/intel_port/metal_cache.py"
                verify --root "${CMAKE_SOURCE_DIR}" --cache "${ALCEDO_PREBUILT_METAL_DIR}"
            RESULT_VARIABLE _alcedo_metal_verify_result
            OUTPUT_VARIABLE _alcedo_metal_verify_stdout
            ERROR_VARIABLE _alcedo_metal_verify_stderr
        )
        if(NOT _alcedo_metal_verify_result EQUAL 0)
            message(FATAL_ERROR "Precompiled Metal pack rejected (outdated or corrupt):\n${_alcedo_metal_verify_stdout}\n${_alcedo_metal_verify_stderr}")
        endif()
        message(STATUS "Reusing verified prebuilt Metal shaders from ${ALCEDO_PREBUILT_METAL_DIR}")
    endif()
'''
    text = text.replace(anchor, prologue, 1)
    # Only require Xcode's Metal compiler when no precompiled library pack was supplied.
    anchor1 = '    find_program(ALCEDO_XCRUN_EXECUTABLE xcrun REQUIRED)\n'
    anchor2 = '    set(ALCEDO_METAL_COMMON_COMPILE_FLAGS\n'
    if text.count(anchor1) != 1 or text.count(anchor2) != 1:
        raise RuntimeError('Upstream xcrun setup anchors changed')
    text = text.replace(anchor1, '    if(NOT ALCEDO_PREBUILT_METAL_DIR)\n' + anchor1, 1)
    text = text.replace(anchor2, '    endif() # Metal command line compiler required only for source builds\n\n' + anchor2, 1)
    # Add the alternate command without altering original source-compile command.
    old = '''        get_filename_component(_air_dir "${air_file}" DIRECTORY)
        set(_depfile "${air_file}.d")

        add_custom_command('''
    new = '''        if(ALCEDO_PREBUILT_METAL_DIR)
            get_filename_component(_shader_basename "${metallib_file}" NAME)
            set(_external_lib "${ALCEDO_PREBUILT_METAL_DIR}/${_shader_basename}")
            if(NOT EXISTS "${_external_lib}")
                message(FATAL_ERROR "Precompiled shader is missing: ${_external_lib}")
            endif()
            get_filename_component(_shader_output_dir "${metallib_file}" DIRECTORY)
            add_custom_command(
                OUTPUT "${metallib_file}"
                COMMAND ${CMAKE_COMMAND} -E make_directory "${_shader_output_dir}"
                COMMAND ${CMAKE_COMMAND} -E copy_if_different "${_external_lib}" "${metallib_file}"
                DEPENDS "${_external_lib}"
                COMMENT "Reusing precompiled Metal library ${_shader_basename}"
                VERBATIM
            )
        else()
            get_filename_component(_air_dir "${air_file}" DIRECTORY)
            set(_depfile "${air_file}.d")

        add_custom_command('''
    if text.count(old) != 1:
        raise RuntimeError('Upstream metal library function anchor changed')
    text = text.replace(old, new, 1)
    end = '''        add_custom_target(${shader_target} DEPENDS "${metallib_file}")'''
    if text.count(end) != 1:
        raise RuntimeError('Upstream shader target anchor changed')
    text = text.replace(end, '        endif() # precompiled vs source-built Metal\n' + end, 1)
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
    print(f'{"Patch validation passed" if args.check else "Installed precompiled Metal CMake integration"}: {target}')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError) as e:
        print(f'Patch failed: {e}', file=sys.stderr)
        sys.exit(1)
