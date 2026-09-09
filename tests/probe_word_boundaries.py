"""Read-only comparison of stored boundaries with local alignment/refinement.

Writes diagnostic clips, never updates the lyrics database.
"""
import copy
import json
import sqlite3
import sys
from pathlib import Path

import soundfile as sf
from faster_whisper import WhisperModel
from stable_whisper.alignment import align, refine

root = Path(__file__).resolve().parents[1]
filename = sys.argv[1]
row_index = int(sys.argv[2])
out = root / 'tests/.artifacts/boundary_probe'
out.mkdir(parents=True, exist_ok=True)
with sqlite3.connect((root / 'assets/favorites.db').as_uri() + '?mode=ro', uri=True) as conn:
    raw = conn.execute('select segments_json from lyrics where file_name=? order by updated_at desc limit 1', (filename,)).fetchone()[0]
segment = json.loads(raw)[row_index]
info = sf.info(root / 'outputs' / filename)
offset = max(0, segment['start'] - .8)
audio, rate = sf.read(root / 'outputs' / filename, start=round(offset * info.samplerate), stop=round((segment['end'] + .8) * info.samplerate), dtype='float32')
sample = out / 'context.wav'
sf.write(sample, audio, rate)
model = WhisperModel(str(root / 'models/whisper/large-v3'), device='cuda', compute_type='float16')
result = align(model, str(sample), segment['text'], language='tr', original_split=True, regroup=False, fast_mode=False, remove_instant_words=False, max_word_dur=None, suppress_silence=True, suppress_word_ts=True, vad=False, verbose=None)
before = copy.deepcopy(result.to_dict())
refined = refine(model, str(sample), result, precision=.02, single_batch=True, inplace=False, verbose=None)
summary = {'offset': offset, 'stored': segment['words'], 'local_alignment': before['segments'], 'refined': refined.to_dict()['segments'], 'note': 'Model comparison only, not verified acoustic ground truth.'}
(out / 'comparison.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
for method, words in [('stored', segment['words']), ('refined', [w for s in summary['refined'] for w in s['words']])]:
    for i, w in enumerate(words):
        start = w['start'] - offset if method == 'stored' else w['start']
        end = w['end'] - offset if method == 'stored' else w['end']
        sf.write(out / f'{method}_{i+1}.wav', audio[max(0, round(start*rate)):round(end*rate)], rate)
print(json.dumps(summary, ensure_ascii=True))
