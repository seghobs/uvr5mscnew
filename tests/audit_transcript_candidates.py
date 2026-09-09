"""Unprompted local ASR comparison; hypotheses only, never edits saved lyrics."""
import json
from pathlib import Path
import soundfile as sf
from faster_whisper import WhisperModel
root=Path(__file__).resolve().parents[1]
out=root/'tests/.artifacts/confidence_audit'
audio=root/'outputs/Ensemble_Vocals_1788641882.flac'
info=sf.info(audio)
model=WhisperModel(str(root/'models/whisper/large-v3'),device='cuda',compute_type='float16')
result=[]
for label,start,end in [('intro',0,8),('uyan',88,97),('inadini',99,107),('outro',126,info.duration)]:
    samples,rate=sf.read(audio,start=int(start*info.samplerate),stop=int(end*info.samplerate),dtype='float32')
    clip=out/(label+'.wav');sf.write(clip,samples,rate)
    decoded,_=model.transcribe(str(clip),language='tr',beam_size=5,temperature=0,condition_on_previous_text=False,vad_filter=False,word_timestamps=False)
    entry={'region':label,'start':start,'end':end,'hypothesis':' '.join(s.text.strip() for s in decoded)}
    result.append(entry);print(json.dumps(entry,ensure_ascii=True),flush=True)
(out/'transcript_hypotheses.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
