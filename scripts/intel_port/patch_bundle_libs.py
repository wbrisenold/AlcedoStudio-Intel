#!/usr/bin/env python3
"""Fix library versions and add missing deps in macOS bundle install(CODE) block."""
from pathlib import Path
import argparse
import sys

REL = Path('CMakeLists.txt')


def patch(text: str) -> str:
    if 'libopencv_core.500.dylib' in text:
        raise RuntimeError('OpenCV 500 version already patched')
    # Update OpenCV from 412 to 500
    old = '''        set(_alcedo_dylib_ids
            \\"libopencv_core.412.dylib=@rpath/libopencv_core.412.dylib\\"
            \\"libopencv_imgproc.412.dylib=@rpath/libopencv_imgproc.412.dylib\\"
            \\"libopencv_imgcodecs.412.dylib=@rpath/libopencv_imgcodecs.412.dylib\\"
            \\"libopencv_features2d.412.dylib=@rpath/libopencv_features2d.412.dylib\\"
            \\"libopencv_flann.412.dylib=@rpath/libopencv_flann.412.dylib\\"
            \\"libgcc_s.1.1.dylib=@rpath/libgcc_s.1.1.dylib\\"
            \\"libjxl_cms.0.11.2.dylib=@rpath/libjxl_cms.0.11.dylib\\"
        )'''
    new = '''        set(_alcedo_dylib_ids
            \\"libopencv_core.500.dylib=@rpath/libopencv_core.500.dylib\\"
            \\"libopencv_imgproc.500.dylib=@rpath/libopencv_imgproc.500.dylib\\"
            \\"libopencv_imgcodecs.500.dylib=@rpath/libopencv_imgcodecs.500.dylib\\"
            \\"libopencv_features2d.500.dylib=@rpath/libopencv_features2d.500.dylib\\"
            \\"libopencv_flann.500.dylib=@rpath/libopencv_flann.500.dylib\\"
            \\"libopencv_geometry.500.dylib=@rpath/libopencv_geometry.500.dylib\\"
            \\"libgcc_s.1.1.dylib=@rpath/libgcc_s.1.1.dylib\\"
            \\"libjxl_cms.0.12.dylib=@rpath/libjxl_cms.0.12.dylib\\"
            \\"libexpat.1.dylib=@rpath/libexpat.1.dylib\\"
            \\"libbrotlicommon.1.dylib=@rpath/libbrotlicommon.1.dylib\\"
        )'''
    if text.count(old) != 1:
        raise RuntimeError('OpenCV/jxl anchor changed')
    text = text.replace(old, new, 1)

    # Add copy+fix for libexpat and libbrotlicommon after libgfortran/libquadmath/libgcc_s
    old = '''        # Ensure the GCC runtime chain exists in the bundle.
        _alcedo_copy_lib_if_missing(\\"libgfortran.5.dylib\\")
        _alcedo_copy_lib_if_missing(\\"libquadmath.0.dylib\\")
        _alcedo_copy_lib_if_missing(\\"libgcc_s.1.1.dylib\\")'''
    new = '''        # Ensure the GCC runtime chain exists in the bundle.
        _alcedo_copy_lib_if_missing(\\"libgfortran.5.dylib\\")
        _alcedo_copy_lib_if_missing(\\"libquadmath.0.dylib\\")
        _alcedo_copy_lib_if_missing(\\"libgcc_s.1.1.dylib\\")
        # Intel CI: additional transitive dependencies from Homebrew Qt/OpenCV
        _alcedo_copy_lib_if_missing(\\"libexpat.1.dylib\\")
        _alcedo_copy_lib_if_missing(\\"libbrotlicommon.1.dylib\\")'''
    if text.count(old) != 1:
        raise RuntimeError('GCC runtime copy anchor changed')
    text = text.replace(old, new, 1)

    # Add Qt framework copy function and invocations after the lib loop
    old = r'''        message(STATUS \"Patched GCC runtime chain for macOS bundle\")
        "
    )

    if(ALCEDO_MACOS_VERIFY_BUNDLE_DEPS)'''
    new = r'''        message(STATUS \"Patched GCC runtime chain for macOS bundle\")

        # Intel CI: copy Qt frameworks that macdeployqt misses
        function(_alcedo_copy_fw_if_missing _fw_name)
            set(_src_dir "${CMAKE_PREFIX_PATH}/lib/${_fw_name}.framework")
            if(EXISTS "${_src_dir}")
                set(_dst_dir "${_alcedo_fw_dir}/${_fw_name}.framework")
                if(NOT EXISTS "${_dst_dir}")
                    execute_process(
                        COMMAND /bin/cp -Rf "${_src_dir}" "${_dst_dir}"
                        RESULT_VARIABLE _copy_result
                    )
                    if(NOT _copy_result EQUAL 0)
                        message(FATAL_ERROR "Failed to copy ${_src_dir} -> ${_dst_dir}")
                    endif()
                endif()
            endif()
        endfunction()

        _alcedo_copy_fw_if_missing("QtDBus")
        _alcedo_copy_fw_if_missing("QtQmlMeta")
        _alcedo_copy_fw_if_missing("QtQmlModels")
        _alcedo_copy_fw_if_missing("QtQmlWorkerScript")
        _alcedo_copy_fw_if_missing("QtQuickControls2Impl")
        _alcedo_copy_fw_if_missing("QtQuickDialogs2QuickImpl")
        _alcedo_copy_fw_if_missing("QtQuickDialogs2Utils")
        _alcedo_copy_fw_if_missing("QtQuickTemplates2")
        _alcedo_copy_fw_if_missing("QtSvg")
        _alcedo_copy_fw_if_missing("QtWidgets")

        # Fix rpaths inside copied Qt frameworks
        foreach(_fw IN ITEMS QtDBus QtQmlMeta QtQmlModels QtQmlWorkerScript QtQuickControls2Impl QtQuickDialogs2QuickImpl QtQuickDialogs2Utils QtQuickTemplates2 QtSvg QtWidgets)
            set(_fw_bin "${_alcedo_fw_dir}/${_fw}.framework/${_fw}")
            if(EXISTS "${_fw_bin}")
                execute_process(COMMAND /bin/chmod u+w "${_fw_bin}" ERROR_QUIET)
                execute_process(
                    COMMAND /usr/bin/install_name_tool -id "@rpath/${_fw}.framework/${_fw}" "${_fw_bin}"
                    RESULT_VARIABLE _id_result
                )
                if(NOT _id_result EQUAL 0)
                    message(WARNING "Failed to set install name for ${_fw_bin}")
                endif()
                execute_process(
                    COMMAND /usr/bin/install_name_tool -change ${CMAKE_PREFIX_PATH}/lib/${_fw}.framework/${_fw} @rpath/${_fw}.framework/${_fw} "${_fw_bin}"
                    RESULT_VARIABLE _change_result
                    ERROR_QUIET
                )
            endif()
        endforeach()

        message(STATUS \"Patched GCC runtime chain for macOS bundle\")
        "
    )

    if(ALCEDO_MACOS_VERIFY_BUNDLE_DEPS)'''
    if text.count(old) != 1:
        raise RuntimeError('GCC runtime status message anchor changed')
    text = text.replace(old, new, 1)

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
    print(f'{"Patch validation passed" if args.check else "Fixed bundle library versions and added missing deps"}: {target}')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError) as e:
        print(f'Patch failed: {e}', file=sys.stderr)
        sys.exit(1)