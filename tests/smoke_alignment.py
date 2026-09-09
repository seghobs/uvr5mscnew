"""Read-only smoke test of local Turkish vocals; does not update lyrics DB."""
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import soundfile as sf
from faster_whisper import WhisperModel
from karaoke_timing import align_lyrics, timing_issues

root = Path(__file__).resolve().parents[1]
out = root / 'tests' / '.artifacts'
out.mkdir(exist_ok=True)
conn = sqlite3.connect((root / 'assets/favorites.db').as_uri() + '?mode=ro', uri=True)
selection = None
for filename, raw in conn.execute('select file_name, segments_json from lyrics order by updated_at desc'):
    file = root / 'outputs' / filename
    if not file.is_file() or 'vocal' not in filename.lower() or filename.startswith('Karaoke_Sync_Test_'):
        continue
    seg = next((s for s in json.loads(raw) if s.get('words') and 2 < s['end'] - s['start'] < 10), None)
    if seg:
        selection = file, seg
        break
if not selection:
    raise SystemExit('No local vocal sample available')
file, seg = selection
info = sf.info(file)
start = max(0, seg['start'] - .5)
end = min(info.duration, seg['end'] + .5)
audio, rate = sf.read(file, start=int(start * info.samplerate), stop=int(end * info.samplerate), dtype='float32')
sample = out / 'alignment_sample.wav'
sf.write(sample, audio, rate)
model_name = sys.argv[1] if len(sys.argv) > 1 else 'large-v3-turbo'
model = WhisperModel(str(root / 'models/whisper' / model_name), device='cuda', compute_type='float16')
result = align_lyrics(model, sample, seg['text'], 'tr')
summary = {
    'model': model_name,
    'audio_seconds': len(audio) / rate,
    'expected_word_count': len(seg['text'].split()),
    'aligned_word_count': sum(len(s['words']) for s in result),
    'issues': timing_issues(result),
    'word_intervals': [[w['start'], w['end']] for s in result for w in s['words']],
    'note': 'Integration smoke only; stored lyrics are not a manually verified timing reference.',
}
(out / f'alignment_smoke_{model_name}.json').write_text(json.dumps(summary, indent=2), encoding='utf8')
print(json.dumps(summary, indent=2))
