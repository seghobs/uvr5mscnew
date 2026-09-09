"""Read-only boundary stability audit; no edits to project or model thresholds."""
import json
import sqlite3
import sys
from pathlib import Path
import soundfile as sf
import torch
import torchaudio.functional as AF
from transformers import Wav2Vec2ForCTC, Wav2Vec2FeatureExtractor
root = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from karaoke_ctc import MODEL_DIR, normalized_words, words_from_spans
from karaoke_timing import timing_issues
out = root / 'tests/.artifacts/confidence_audit'
out.mkdir(parents=True,exist_ok=True)
with sqlite3.connect((root/'assets/favorites.db').as_uri()+'?mode=ro',uri=True) as conn:
    record = conn.execute('select file_name,segments_json,updated_at from lyrics where file_name like ? order by updated_at desc limit 1',('%1788641882%',)).fetchone()
segments = json.loads(record[1])
(out/'snapshot.json').write_text(record[1],encoding='utf8')
audio_path = root/'outputs/Ensemble_Vocals_1788641882.flac'
info = sf.info(audio_path)
vocab = json.loads((MODEL_DIR/'vocab.json').read_text(encoding='utf8'))
inv = {v:k for k,v in vocab.items()}
model = Wav2Vec2ForCTC.from_pretrained(MODEL_DIR,local_files_only=True).eval().to('cuda')
extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_DIR,local_files_only=True)
rows = []
for i,seg in enumerate(segments):
    flagged = [j for j,w in enumerate(seg.get('words',[])) if w.get('needs_review')]
    if not flagged: continue
    normalized = normalized_words(seg['words'],vocab)
    ids = [vocab[c] for c in '|'.join(normalized)]
    variants=[]
    for padding in (.4,1.2):
        first = int(max(0,seg['start']-padding)*info.samplerate)
        last = int(min(info.duration,seg['end']+padding)*info.samplerate)
        audio,rate = sf.read(audio_path,start=first,stop=last,dtype='float32')
        if audio.ndim==2: audio=audio.mean(axis=1)
        wave=AF.resample(torch.from_numpy(audio),rate,16000)
        inputs=extractor(wave.numpy(),sampling_rate=16000,return_tensors='pt')
        with torch.inference_mode():
            emission=model(**{k:v.to('cuda') for k,v in inputs.items()}).logits.log_softmax(-1).cpu()
        path,scores=AF.forced_align(emission,torch.tensor([ids],dtype=torch.int32),blank=0)
        spans=AF.merge_tokens(path[0],scores[0].exp(),blank=0)
        result=words_from_spans(seg['words'],normalized,spans,ids,len(wave)/16000/emission.shape[1],first/rate)
        greedy=''.join(inv[t] for t in torch.unique_consecutive(emission[0].argmax(-1)).tolist() if t!=0).replace('|',' ')
        variants.append({'padding':padding,'words':result,'unforced_text':greedy})
    for j in flagged:
        w=seg['words'][j]
        alternatives=[v['words'][j] for v in variants]
        starts=[w['start']]+[a['start'] for a in alternatives]
        ends=[w['end']]+[a['end'] for a in alternatives]
        rows.append({'row':i+1,'word_index':j+1,**w,'context':seg['text'],
                     'start_spread_ms':round((max(starts)-min(starts))*1000,1),
                     'end_spread_ms':round((max(ends)-min(ends))*1000,1),
                     'alternatives':alternatives,'unforced_text':[v['unforced_text'] for v in variants]})
    print(f'row {i+1}: {len(flagged)} warnings compared',flush=True)
summary={'snapshot_updated':record[2],'structural_errors':timing_issues(segments,include_review=False),
         'word_count':sum(len(s.get('words',[])) for s in segments),'rows':rows,
         'note':'Context sensitivity, NOT accuracy versus human ground truth; unforced CTC text is not a verified transcript.'}
(out/'audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps([{k:r[k] for k in ('row','word_index','word','probability','start_spread_ms','end_spread_ms')} for r in rows],ensure_ascii=True))
