import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import json

ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name, ROOT/'scripts/intel_port'/f'{name}.py')
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module

metal=load('metal_cache')
patcher=load('apply_port')

class PortTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        parent=self.root/'alcedo_studio/src'
        parent.joinpath('metal').mkdir(parents=True)
        parent.joinpath('edit/runtime/metal/shader').mkdir(parents=True)
        lines=['# Metal target ownership', 'if(ALCEDO_METAL_ENABLED)',
          '    find_program(ALCEDO_XCRUN_EXECUTABLE xcrun REQUIRED)',
          '    execute_process(COMMAND ${ALCEDO_XCRUN_EXECUTABLE} --sdk macosx --find metal)',
          '    set(ALCEDO_METAL_COMMON_COMPILE_FLAGS', '        -MMD', '    )',
          '    function(alcedo_add_metal_library shader_target source_file air_file metallib_file compile_comment link_comment)',
          '        get_filename_component(_air_dir "${air_file}" DIRECTORY)',
          '        set(_depfile "${air_file}.d")',
          '',
          '        add_custom_command(',
          '            OUTPUT "${air_file}"',
          '        )',
          '        add_custom_command(',
          '            OUTPUT "${metallib_file}"',
          '            DEPENDS "${air_file}"',
          '        )',
          '        add_custom_target(${shader_target} DEPENDS "${metallib_file}")',
          '        set_property(GLOBAL APPEND PROPERTY ALCEDO_METAL_RUNTIME_LIB_FILES "${metallib_file}")',
          '    endfunction()']
        for i in range(17):
            name=f'METAL_UNIT{i}_SRC'
            lines.append(f'    set({name} "${{ALCEDO_SRC_ROOT}}/edit/runtime/metal/shader/u{i}.metal")')
            lines += ['    alcedo_add_metal_library(', f'        Shader{i}', f'        "${{{name}}}"', f'        "${{ALCEDO_BINARY_ROOT}}/u{i}.air"',f'        "${{ALCEDO_BINARY_ROOT}}/u{i}.metallib"','        "compile"','        "link"', '    )']
            parent.joinpath(f'edit/runtime/metal/shader/u{i}.metal').write_text(f'kernel void u{i}() {{}}\n')
        lines.append('endif()')
        (self.root/metal.METAL_CMAKE).write_text('\n'.join(lines)+'\n')
    def test_detect_library_set(self):
        self.assertEqual(len(metal.sources(self.root)),17)
        self.assertIn('u0.metallib',metal.sources(self.root))
    def test_patch_preserves_original_path(self):
        text=(self.root/metal.METAL_CMAKE).read_text()
        converted=patcher.patch(text)
        self.assertIn('if(NOT ALCEDO_PREBUILT_METAL_DIR)',converted)
        self.assertIn('Reusing precompiled Metal library',converted)
        self.assertIn('COMMAND ${CMAKE_COMMAND} -E copy_if_different',converted)
        self.assertIn('COMMAND ${CMAKE_COMMAND} -E copy_if_different',converted)
        self.assertIn('if(NOT _alcedo_metal_verify_result EQUAL 0)',converted)
        with self.assertRaises(RuntimeError): patcher.patch(converted)
    def test_verify_detects_changed_shader_and_corruption(self):
        out=self.root/'cache';out.mkdir()
        entries=[]
        for name,p in metal.sources(self.root).items():
            binary=out/name
            binary.write_bytes(b'compiled-test' * 20)
            entries.append({'file':name,'sha256':metal.sha256(binary),'bytes':binary.stat().st_size,
                           'inputs': {metal.repo_rel(self.root,p):metal.sha256(p)}})
        (out/metal.MANIFEST).write_text(json.dumps({'schema':1,'platform':'macos','deployment_target':'13.3','libraries':entries}))
        metal.verify(self.root,out)
        p=next(iter(metal.sources(self.root).values()))
        p.write_text('changed source\n')
        with self.assertRaisesRegex(ValueError,'Shader input changed'):
            metal.verify(self.root,out)
        p.write_text('kernel void u0() {}\n')
        (out/'u0.metallib').write_text('tamper')
        with self.assertRaisesRegex(ValueError,'tampered'):
            metal.verify(self.root,out)
    def test_compiler_pack_and_extract_via_stub(self):
        from unittest.mock import patch
        import zipfile
        calls=[]
        def fake_run(command, **kwargs):
            calls.append(command)
            if 'metal' in command:
                Path(command[-1]).write_bytes(b'fake AIR' * 20)
            if 'metallib' in command:
                Path(command[-1]).write_bytes(b'fake metallib' * 20)
            return subprocess.CompletedProcess(command,0)
        archive=self.root/'metal.zip'
        def fake_check_output(command,**kwargs):
            return 'fixture-commit\n' if 'rev-parse' in command else 'https://github.com/zidage/AlcedoStudio.git\n'
        with patch.object(metal.subprocess,'run',side_effect=fake_run), patch.object(metal.subprocess,'check_output',side_effect=fake_check_output):
            metal.compile_all(self.root,self.root/'out','13.3',archive)
        self.assertEqual(len(calls),34)
        self.assertTrue(archive.is_file())
        metal.extract(archive,self.root/'reused')
        metal.verify(self.root,self.root/'reused')
        self.assertEqual(len(list((self.root/'reused').glob('*.metallib'))),17)

    def test_archive_rejects_unexpected_file(self):
        import zipfile
        archive=self.root/'bad.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('../malicious','payload')
        with self.assertRaisesRegex(ValueError,'Unexpected archive member'):
            metal.extract(archive,self.root/'output')
    def test_cache_manifest_defensively_requires_expected_macos_minimum(self):
        p=self.root/'cache';p.mkdir()
        (p/metal.MANIFEST).write_text(json.dumps({'schema':1,'platform':'macos','deployment_target':'14.0','libraries':[]}))
        with self.assertRaisesRegex(ValueError,'13.3'):
            metal.verify(self.root,p)

if __name__=='__main__': unittest.main(verbosity=2)
