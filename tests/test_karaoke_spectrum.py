import shutil
import subprocess
import unittest
from pathlib import Path

import numpy as np

from karaoke_spectrum import velocity_filter


class SpectrumTests(unittest.TestCase):
    def test_modulated_bass_moves_without_duplicating_or_pinning_leading_bars(self):
        bundled = Path('tools/setup-runtime/ffmpeg/bin/ffmpeg.exe')
        ffmpeg = str(bundled) if bundled.exists() else shutil.which('ffmpeg')
        if not ffmpeg:
            self.skipTest('FFmpeg required')
        # A 60 Hz tone whose amplitude changes: only the first band should lead,
        # and its height must follow the change instead of staying clipped.
        source = 'aevalsrc=0.08*(1+0.8*sin(2*PI*2*t))*sin(2*PI*60*t):s=16000:d=3'
        run = subprocess.run([
            ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', source,
            '-filter_complex', velocity_filter(fps=30)+',format=gray',
            '-an', '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1',
        ], capture_output=True, check=True)
        frames = np.frombuffer(run.stdout, np.uint8).reshape(-1, 80, 80)
        heights = (frames > 100).sum(axis=1)[5:]
        self.assertGreater(np.ptp(heights[:, 0]), 8)
        self.assertLess(heights[:, :12].max(), 79)
        self.assertGreater(heights[:, 0].mean(), heights[:, 3:12].mean()+8)
