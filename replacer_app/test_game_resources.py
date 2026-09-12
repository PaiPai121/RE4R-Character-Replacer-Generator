import unittest
import tempfile
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch
import game_resources as resources


class ResourceTests(unittest.TestCase):
    def test_resource_paths_cannot_escape(self):
        for path in ('../game.exe','C:/game.exe','natives/stm/../../game.exe','/natives/stm/a'):
            with self.assertRaises(ValueError):resources.safe_resource(path)
        self.assertEqual(resources.safe_resource(r'natives\stm\MODEL.mesh'),'natives/stm/model.mesh')

    def test_patch_order_is_numeric(self):
        names=['re_chunk_000.patch_010.pak','re_chunk_000.pak','re_chunk_000.patch_002.pak']
        self.assertEqual(sorted(names,key=lambda n:resources.pak_order(Path(n))),[names[1],names[2],names[0]])

    def test_catalog_does_not_mix_luis_with_krauser(self):
        luis=next(c for c in resources.CHARACTERS if c['id']=='luis')
        self.assertEqual(luis['characterIds'],['cha300'])

    def test_empty_patch_scan_is_success(self):
        result=CompletedProcess([],0,stdout='[]',stderr='Found 0/100 target files')
        self.assertEqual(resources.parse_scan_result(result),[])

    def test_failed_patch_scan_is_not_silently_ignored(self):
        result=CompletedProcess([],2,stdout='',stderr='invalid PAK')
        with self.assertRaisesRegex(RuntimeError,'invalid PAK'):
            resources.parse_scan_result(result)

    def test_invalid_scan_json_is_rejected(self):
        result=CompletedProcess([],0,stdout='Found 0/100 target files',stderr='')
        with self.assertRaisesRegex(RuntimeError,'无效数据'):
            resources.parse_scan_result(result)

    def test_fluffy_invalidated_primary_is_diagnosed_from_loose_file(self):
        with tempfile.TemporaryDirectory() as directory:
            game = Path(directory)
            primary = 'natives/stm/_chainsaw/character/ch/cha0/cha000/00/cha000_00.mesh.221108797'
            mdf = 'natives/stm/_chainsaw/character/ch/cha0/cha000/00/cha000_00.mdf2.32'
            loose = game / primary
            loose.parent.mkdir(parents=True)
            loose.touch()
            diagnostics = resources.build_scan_diagnostics(game, [primary, mdf], {})
            leon = diagnostics['characters']['leon']
            self.assertFalse(leon['primaryAvailable'])
            self.assertEqual(leon['issue'], 'modded-game-archive')
            self.assertEqual(leon['loosePrimary'], [primary])

    def test_extract_failure_reports_archive_batch_and_missing_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            game = root / 'game'
            destination = root / 'work' / 'reference'
            game.mkdir()
            pak = game / 're_chunk_000.pak'
            pak.touch()
            path = 'natives/stm/example.mesh.221108797'
            data = {'game': str(game), 'resources': {path: {'pak': pak.name, 'size': 1}}}
            failed = CompletedProcess([], 1, stdout='Found 0/1 target files', stderr='')
            with patch.object(resources, 'ROOT', root), patch.object(resources.subprocess, 'run', return_value=failed):
                with self.assertRaisesRegex(RuntimeError, 're_chunk_000.pak.*批次 1/1.*example.mesh'):
                    resources.extract(data, [path], destination)


if __name__=='__main__':unittest.main()
