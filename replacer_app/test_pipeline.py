import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
import pipeline


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pose = self.root / 'work/manual.blend'
        self.pose.parent.mkdir()
        self.pose.write_bytes(b'actual user saved pose')
        self.project = {'files': {'poseBlend': str(self.pose)}, 'sourceModel': 'custom.fbx',
                        'targetProfile': {'bodySlots': {'cha000':['00']}}}
        self.build_root = self.root / 'j'
        self.root_patch = patch.object(pipeline, 'ROOT', self.root)
        self.root_patch.start()
        self.environment_patch = patch.dict(os.environ, {'REPLACER_BUILD_ROOT': str(self.build_root)})
        self.environment_patch.start()

    def tearDown(self):
        self.environment_patch.stop()
        self.root_patch.stop()
        self.temp.cleanup()

    def test_rejects_outside_workspace(self):
        self.project['files']['poseBlend'] = str(self.root / 'outside.blend')
        with self.assertRaises(ValueError):
            pipeline.run(self.project, 'unused', {})

    def test_failed_worker_never_returns_old_archive(self):
        old = self.root / 'mod/old.zip'
        old.parent.mkdir()
        old.write_bytes(b'old artifact')
        with patch.object(pipeline.subprocess, 'Popen') as launch:
            launch.return_value.poll.return_value = 1
            launch.return_value.returncode = 1
            with self.assertRaises(RuntimeError):
                pipeline.run(self.project, 'unused', {})
        self.assertEqual(old.read_bytes(), b'old artifact')
        self.assertFalse(list((self.root/'work').rglob('*.zip')))
        request = json.loads(next(self.build_root.rglob('request.json')).read_text())
        self.assertEqual(Path(request['input']).read_bytes(), self.pose.read_bytes())
        self.assertEqual(Path(request['originalBlend']).resolve(), self.pose.resolve())

    def test_intermediate_build_path_is_short_even_when_project_root_is_deep(self):
        deep_root = self.root / ('very-long-release-directory-' * 5)
        with patch.object(pipeline, 'ROOT', deep_root):
            work = pipeline.create_build_directory()
        self.assertEqual(work.parent, self.build_root.resolve())
        self.assertEqual(len(work.name), 8)
        representative = work / 'package/natives/stm/_Chainsaw/Character/ch/Replacer' / work.name / 'Material_000_ALBD.tex.143221013'
        self.assertLess(len(str(representative)), 240)

    def test_pose_changed_during_snapshot_is_rejected(self):
        with patch.object(pipeline, 'digest', side_effect=['first','second']):
            with self.assertRaises(ValueError):
                pipeline.run(self.project, 'unused', {})

    def test_build_routes_unicode_input_through_compatible_packager(self):
        self.project['sourceModel'] = '\u5361\u8299\u53613.0.pmx'
        self.project['targetProfile'].update(id='leon', label='\u91cc\u6602')

        def worker(blender, script, request, work, job, stage):
            if stage == 'build':
                (work / 'validation_request.json').write_text('{}')
                return
            package = work / 'package'
            (package / 'natives/stm').mkdir(parents=True)
            (package / 'natives/stm/test.mesh').write_bytes(b'model payload')
            (package / 'modinfo.ini').write_text('name=\u5361\u8299\u5361\nversion=0.2\n', encoding='utf-8')
            (work / 'result.json').write_text(json.dumps({
                'passed': True, 'source_sha256': pipeline.digest(self.pose)}))

        with patch.object(pipeline, 'run_blender_stage', side_effect=worker):
            result = pipeline.run(self.project, 'unused', {})
        archive = Path(result['packageZip'])
        self.assertTrue(archive.name.isascii())
        self.assertEqual(json.loads((archive.parent / 'release.json').read_text())['packageZip'], str(archive))
        with zipfile.ZipFile(archive) as z:
            self.assertTrue(all(i.filename.isascii() and i.flag_bits == 0 for i in z.infolist()))
            self.assertEqual(z.read(archive.stem + '/natives/stm/test.mesh'), b'model payload')
            z.read(archive.stem + '/modinfo.ini').decode('ascii')


if __name__ == '__main__':
    unittest.main()
