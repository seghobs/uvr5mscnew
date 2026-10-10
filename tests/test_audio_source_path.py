import tempfile
import unittest
from pathlib import Path
from audio_source_path import resolve_legacy_source


class SourcePathTests(unittest.TestCase):
    def test_exact_unicode_title(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'Gözleri Fettan Güzel #müslümgürses.wav'
            source.touch()
            self.assertEqual(resolve_legacy_source(source.stem, [folder], ['.wav']), source.resolve())

    def test_ambiguous_title_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for extension in ['.wav', '.mp3']:
                (Path(folder) / ('song' + extension)).touch()
            with self.assertRaises(ValueError):
                resolve_legacy_source('song', [folder], ['.wav', '.mp3'])

    def test_missing_explicit_path_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'song.wav').touch()
            missing = str(Path(folder) / 'missing' / 'song.wav')
            self.assertEqual(resolve_legacy_source(missing, [folder], ['.wav']), Path(missing).resolve())
