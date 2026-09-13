import tempfile
import unittest
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from video_filename import video_stem, reserve_video_path


class VideoFilenameTests(unittest.TestCase):
    def test_requested_format_and_turkish(self):
        self.assertEqual(video_stem('Berdan Mardini', 'Berfin', 'Orjinal Karaoke'),
                         'Berdan Mardini - Berfin ( Orjinal Karaoke )')
        self.assertEqual(video_stem('Özgür', 'Şarkı', '( Türkçe Karaoke )'),
                         'Özgür - Şarkı ( Türkçe Karaoke )')

    def test_empty_fields_and_windows_unsafe_names(self):
        self.assertEqual(video_stem(title='Berfin'), 'Berfin')
        self.assertEqual(video_stem(fallback='Instrumental'), 'Instrumental')
        self.assertEqual(video_stem(title='CON'), '_CON')
        name = video_stem('../A:rtist', 'song?\\name/#%', 'a\nb*')
        self.assertFalse(any(c in name for c in '<>:"/\\|?*\n'))
        self.assertNotIn('..', name)
        self.assertLessEqual(len(video_stem(title='ş'*500).encode('utf8')), 200)

    def test_concurrent_renders_never_overwrite_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory)/'Artist - Song ( Karaoke ).mp4'
            existing.write_bytes(b'previous video')
            with ThreadPoolExecutor(max_workers=4) as pool:
                paths = list(pool.map(lambda _: reserve_video_path(directory,
                    artist='Artist', title='Song', label='Karaoke'), range(4)))
            self.assertEqual(len(set(paths)), 4)
            self.assertEqual(existing.read_bytes(), b'previous video')
            self.assertEqual({p.name for p in paths}, {
                f'Artist - Song ( Karaoke ) ({i}).mp4' for i in range(2,6)})

    def test_ffmpeg_writes_video_with_turkish_and_url_characters(self):
        portable = Path(__file__).resolve().parents[1]/'tools/setup-runtime/ffmpeg/bin/ffmpeg.exe'
        ffmpeg = str(portable) if portable.exists() else shutil.which('ffmpeg')
        if not ffmpeg: self.skipTest('FFmpeg not installed')
        with tempfile.TemporaryDirectory() as directory:
            target = reserve_video_path(directory, artist='Özgür', title='Şarkı #1 %', label='Orjinal Karaoke')
            subprocess.run([ffmpeg, '-v', 'error', '-y', '-f', 'lavfi', '-i',
                'color=c=black:s=64x64:r=10', '-t', '0.2', '-c:v', 'libx264', target.name],
                cwd=directory, capture_output=True, check=True, timeout=30)
            self.assertGreater(target.stat().st_size, 100)


if __name__ == '__main__': unittest.main()
