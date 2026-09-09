"""Read-only acoustic inspection of the reported row; writes diagnostic crops only."""
import json
from pathlib import Path
import soundfile as sf
from faster_whisper import WhisperModel

root = Path(__file__).resolve().parents[1]
out = root / 'tests/.artifacts'
out.mkdir(exist_ok=True)
source = root / 'outputs/Ensemble_Vocals_1788631857.flac'
info = sf.info(source)
model = WhisperModel(str(root / 'models/whisper/large-v3-turbo'), device='cuda', compute_type='float16', local_files_only=True)
results = []
for start, end in [(3, 12), (42, 51)]:
    data, rate = sf.read(source, start=round(start*info.samplerate), stop=round(end*info.samplerate))
    crop = out / f'yagmur_{start}_{end}.wav'
    sf.write(crop, data, rate)
    segments, _ = model.transcribe(str(crop), language='tr', word_timestamps=True, vad_filter=False, condition_on_previous_text=False)
    words = [{'word':w.word,'start':w.start+start,'end':w.end+start,'probability':w.probability} for s in segments for w in s.words]
    result = {'crop':[start,end], 'words':words}
    results.append(result)
    print(json.dumps(result, ensure_ascii=True), flush=True)
(out / 'yagmur_audio_inspection.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
del model
import sqlite3
import sys
sys.path.insert(0, str(root))
from karaoke_ctc import refine_turkish
with sqlite3.connect(root / 'assets/favorites.db') as db:
    row = json.loads(db.execute('select segments_json from lyrics where file_key=?', ('ensemble_vocals_1788631857',)).fetchone()[0])[0]
row['start'], row['end'] = 43.5, 49.5
aligned = refine_turkish(source, [row], 'tr')
(out / 'yagmur_ctc_inspection.json').write_text(json.dumps(aligned,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'ctc':aligned},ensure_ascii=True),flush=True)
