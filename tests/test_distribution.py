"""Distribution integrity: wrong/missing/traversing pieces cannot clobber a build."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.assemble_build import assemble


class DistributionTests(unittest.TestCase):
    def fixture(self, root):
        payloads = [b'first source block\0' * 83, b'next block\xff' * 59]
        parts = []
        for index, data in enumerate(payloads):
            name = 'test.tar.gz.part' + str(index)
            (root / name).write_bytes(data)
            parts.append({'file': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        full = b''.join(payloads)
        value = {'archive': 'test.tar.gz', 'bytes': len(full), 'sha256': hashlib.sha256(full).hexdigest(), 'parts': parts}
        manifest = root / 'parts.json'
        manifest.write_text(json.dumps(value))
        return manifest, value, full

    def test_verified_parts_restore_exact_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest, _, full = self.fixture(root)
            output = assemble(manifest)
            self.assertEqual(output.read_bytes(), full)
            self.assertFalse(list(root.glob('*.partial')))

    def test_invalid_parts_preserve_previous_archive_and_remove_partial_output(self):
        for failure in ('changed', 'missing', 'traversal', 'duplicate', 'final_hash'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                manifest, value, _ = self.fixture(root)
                target = root / 'test.tar.gz'
                target.write_bytes(b'previous build')
                part = root / value['parts'][0]['file']
                if failure == 'changed': part.write_bytes(b'changed source')
                if failure == 'missing': part.unlink()
                if failure == 'traversal': value['parts'][0]['file'] = '../escape'
                if failure == 'duplicate': value['parts'][1]['file'] = value['parts'][0]['file']
                if failure == 'final_hash': value['sha256'] = '0' * 64
                manifest.write_text(json.dumps(value))
                with self.assertRaises((ValueError, FileNotFoundError)):
                    assemble(manifest)
                self.assertEqual(target.read_bytes(), b'previous build')
                self.assertFalse(list(root.glob('*.partial')))
