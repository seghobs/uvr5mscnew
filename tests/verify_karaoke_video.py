"""Inspect the rendered synthetic integration fixture, including the silent gap."""
import json
import re
import subprocess
import sys
from pathlib import Path
import numpy as np

video = Path(sys.argv[1]) if len(sys.argv) > 1 else max(Path('outputs').glob('Karaoke_Karaoke_Sync_Test*.mp4'), key=lambda p: p.stat().st_mtime)
counts = []
for time in [1.2, 1.3, 1.4, 1.8, 2.5, 3.0, 3.2, 3.7]:
    result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-ss', str(time),
        '-frames:v', '1', '-vf', 'crop=500:120:710:550', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
        capture_output=True, check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    pixels = np.frombuffer(result.stdout, dtype=np.uint8).reshape(120, 500, 3)
    gold = (pixels[:, :, 0] > 150) & (pixels[:, :, 1] > 110) & (pixels[:, :, 2] < 90)
    counts.append([time, int(gold.sum())])
assert counts[0][1] == counts[1][1] == 0
assert counts[3][1] > 0
assert abs(counts[4][1] - counts[3][1]) < 20
assert abs(counts[5][1] - counts[3][1]) < 20
assert counts[7][1] > counts[6][1] > counts[5][1]
probe = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(video)], capture_output=True, text=True,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
assert re.search(r'60 fps', probe.stderr), probe.stderr
summary = {'file': str(video), 'fps': 60, 'yellow_pixels': counts,
           'result': 'No early fill; no movement during the gap; both words finish.'}
Path('tests/.artifacts/video_verification.json').write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
