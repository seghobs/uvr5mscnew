"""Local-only Turkish CTC boundary experiment; never writes lyrics records."""
import json
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio.functional as AF
from transformers import Wav2Vec2ForCTC, Wav2Vec2FeatureExtractor

root = Path(__file__).resolve().parents[1]
out = root / 'tests/.artifacts/boundary_probe'
data = json.loads((out / 'comparison.json').read_text(encoding='utf-8'))
model_dir = root / 'models/alignment/turkish-ctc'
vocab = json.loads((model_dir / 'vocab.json').read_text(encoding='utf-8'))
words = [w['word'] for w in data['stored']]
normalized = [''.join(c for c in w.replace('I', 'ı').replace('İ', 'i').lower() if c in vocab and len(c) == 1) for w in words]
transcript = '|'.join(normalized)
audio, rate = sf.read(out / 'context.wav', dtype='float32')
if audio.ndim == 2:
    audio = audio.mean(axis=1)
wave = AF.resample(torch.from_numpy(audio), rate, 16000)
extractor = Wav2Vec2FeatureExtractor.from_pretrained(model_dir, local_files_only=True)
model = Wav2Vec2ForCTC.from_pretrained(model_dir, local_files_only=True).eval().to('cuda')
inputs = extractor(wave.numpy(), sampling_rate=16000, return_tensors='pt')
with torch.inference_mode():
    emissions = model(**{k:v.to('cuda') for k,v in inputs.items()}).logits.log_softmax(-1).cpu()
targets = torch.tensor([[vocab[c] for c in transcript]], dtype=torch.int32)
path, scores = AF.forced_align(emissions, targets, blank=0)
spans = AF.merge_tokens(path[0], scores[0].exp(), blank=0)
assert [s.token for s in spans] == targets[0].tolist()
scale = len(wave) / 16000 / emissions.shape[1]
cursor = 0
result = []
for i, word in enumerate(normalized):
    chars = spans[cursor:cursor+len(word)]
    cursor += len(word) + 1
    start, end = chars[0].start * scale, chars[-1].end * scale
    result.append({'word':words[i], 'start':start+data['offset'], 'end':end+data['offset'], 'score':float(np.mean([c.score for c in chars])), 'characters':[{'token':c.token,'start':c.start*scale+data['offset'],'end':c.end*scale+data['offset'],'score':c.score} for c in chars]})
    sf.write(out / f'ctc_{i+1}.wav', audio[round(start*rate):round(end*rate)], rate)
inverse = {v:k for k,v in vocab.items()}
greedy = torch.unique_consecutive(emissions[0].argmax(-1)).tolist()
summary = {'words':result,'recognized':''.join(inverse[t] for t in greedy if t != 0),'note':'Experimental acoustic model output, not ground truth.'}
(out / 'ctc_comparison.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=True))
