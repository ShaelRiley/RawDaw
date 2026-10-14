"""Distribution inventory admits declared demos and rejects unsafe identities."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import source_catalog


class SourceCatalogInventory(unittest.TestCase):
    def catalog(self,root,entries):
        folder=root/'recipes';folder.mkdir(exist_ok=True)
        (folder/'catalog.json').write_text(json.dumps(['sources.json']))
        (folder/'sources.json').write_text(json.dumps(entries))

    def test_new_source_can_supply_short_auditions_without_advertising_a_missing_full_song(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.catalog(root,[dict(packId='existing'),dict(packId='shop_vac',demonstrationSuffixes=['a','b'])])
            with patch.object(source_catalog,'ROOT',root):
                projects=source_catalog.projects()
            self.assertEqual({path.name for path in projects},{'existing_a.prdeproj','existing_b.prdeproj','existing_full.prdeproj','shop_vac_a.prdeproj','shop_vac_b.prdeproj'})
            self.assertTrue(all(path.parent==root/'packs' for path in projects))

    def test_unsafe_or_duplicate_pack_and_demo_paths_fail_before_packaging(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            cases=[dict(packId='../outside'),dict(packId='/outside'),dict(packId='safe',demonstrationSuffixes=['../outside']),
                   dict(packId='safe',demonstrationSuffixes=['a','a']),dict(packId='safe',demonstrationSuffixes=[]),
                   dict(packId='safe',demonstrationSuffixes='a')]
            for entry in cases:
                self.catalog(root,[entry])
                with self.subTest(entry=entry),patch.object(source_catalog,'ROOT',root),self.assertRaises(ValueError):
                    source_catalog.projects()
            self.catalog(root,[dict(packId='same'),dict(packId='same')])
            with patch.object(source_catalog,'ROOT',root),self.assertRaises(ValueError):source_catalog.recipes()


if __name__=='__main__':unittest.main()
