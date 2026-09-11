import tempfile
import unittest
import zipfile
from pathlib import Path
from fluffy_package import package_name, write_package, repair_archive


class PackageTests(unittest.TestCase):
    def test_unicode_source_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            name = package_name('\u5361\u8299\u53613.0.pmx', 'leon', '123456789012')
            output = Path(temp) / (name + '.zip')
            payload = {'modinfo.ini': 'name=\u5361\u8299\u5361\nversion=0.2\n'.encode(),
                       'natives/stm/body.mesh': b'unchanged mesh'}
            write_package(payload, output)
            with zipfile.ZipFile(output) as z:
                self.assertIsNone(z.testzip())
                self.assertTrue(all(i.filename.isascii() and i.flag_bits == 0 for i in z.infolist()))
                self.assertEqual(z.read(name + '/natives/stm/body.mesh'), b'unchanged mesh')
                z.read(name + '/modinfo.ini').decode('ascii')

    def test_repair_preserves_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp)/'old.zip', Path(temp)/'Fixed.zip'
            with zipfile.ZipFile(source, 'w') as z:
                z.writestr('\u5361/modinfo.ini', 'name=old')
                z.writestr('\u5361/natives/stm/a.tex', b'texture')
            original = source.read_bytes()
            repair_archive(source, output)
            self.assertEqual(source.read_bytes(), original)
            with zipfile.ZipFile(output) as z:
                self.assertEqual(z.read('Fixed/natives/stm/a.tex'), b'texture')

    def test_rejects_unsafe_and_case_duplicate_paths(self):
        for rel in ('../escape', 'natives/A', 'natives/\u5361'):
            with self.subTest(rel=rel), tempfile.TemporaryDirectory() as temp:
                with self.assertRaises(ValueError):
                    write_package({'modinfo.ini': b'name=a', 'natives/a': b'a', rel:b'b'},
                                  Path(temp)/'Test.zip')


if __name__ == '__main__':
    unittest.main()
