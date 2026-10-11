import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from prde1 import __version__
from tools.install_renderer import ensure, install


class RendererInstallation(unittest.TestCase):
    def fixture(self,folder,*,wrong_hash=False,linked=False):
        name='PRDE1_'+__version__+'_Linux_x86_64'
        # Explicit transport fixture, not an executable music engine or an audition.
        data=b'\x7fELF\x02\x01'+b'\0'*12+b'\x3e\x00'+b'transport fixture'
        metadata=dict(version=__version__,files={'build/prde1-render':dict(bytes=len(data),sha256='0'*64 if wrong_hash else hashlib.sha256(data).hexdigest())})
        buffer=io.BytesIO()
        with tarfile.open(fileobj=buffer,mode='w:gz') as archive:
            raw=json.dumps(metadata).encode();entry=tarfile.TarInfo(name+'/BUILD_INFO.json');entry.size=len(raw);archive.addfile(entry,io.BytesIO(raw))
            entry=tarfile.TarInfo(name+'/build/prde1-render')
            if linked:entry.type=tarfile.SYMTYPE;entry.linkname='/etc/passwd';archive.addfile(entry)
            else:entry.size=len(data);archive.addfile(entry,io.BytesIO(data))
        blob=buffer.getvalue();part=folder/'fixture.part01';part.write_bytes(blob)
        (folder/'identity.json').write_text(json.dumps(metadata))
        manifest=folder/'fixture.json';manifest.write_text(json.dumps(dict(version=__version__,archive=name+'.tar.gz',bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),
            parts=[dict(file=part.name,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest())])))
        return manifest,data

    def test_installs_only_the_bound_binary_with_executable_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest,data=self.fixture(root);destination=root/'build/renderer'
            install(manifest,destination);self.assertEqual(destination.read_bytes(),data);self.assertEqual(destination.stat().st_mode&0o777,0o755)

    def test_bad_hash_or_link_preserves_prior_completed_renderer(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);destination=root/'renderer';destination.write_bytes(b'previous verified renderer')
            for options in (dict(wrong_hash=True),dict(linked=True)):
                with self.subTest(options=options):
                    manifest,_=self.fixture(root,**options)
                    with self.assertRaises(ValueError):install(manifest,destination)
                    self.assertEqual(destination.read_bytes(),b'previous verified renderer');self.assertFalse(list(root.glob('*.partial')))

    def test_ensure_upgrades_existing_executable_and_reuses_without_archive_or_parts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest,data=self.fixture(root);destination=root/'renderer'
            destination.write_bytes(b'old executable');destination.chmod(0o755)
            path,updated=ensure(manifest,destination,root/'identity.json')
            self.assertTrue(updated);self.assertEqual(path.read_bytes(),data)
            for entry in root.glob('*.part01'):entry.unlink()
            for entry in root.glob('*.tar.gz'):entry.unlink()
            _,updated=ensure(manifest,destination,root/'identity.json')
            self.assertFalse(updated);self.assertEqual(destination.read_bytes(),data)

    def test_identity_disagreement_preserves_previous_renderer(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest,_=self.fixture(root);destination=root/'renderer'
            previous=b'previous completed executable';destination.write_bytes(previous);destination.chmod(0o755)
            info=json.loads((root/'identity.json').read_text());info['files']['build/prde1-render']['sha256']='0'*64
            (root/'identity.json').write_text(json.dumps(info))
            with self.assertRaisesRegex(ValueError,'identity'):ensure(manifest,destination,root/'identity.json')
            self.assertEqual(destination.read_bytes(),previous);self.assertFalse(list(root.glob('*.partial')))


if __name__=='__main__':unittest.main()
