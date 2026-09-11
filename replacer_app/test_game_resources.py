import unittest
from pathlib import Path
from subprocess import CompletedProcess
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


if __name__=='__main__':unittest.main()
