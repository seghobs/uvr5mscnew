"""Local CPU lyric-leak diagnostic. ASR non-detection is NOT proof of no voice."""
import argparse
import json
from pathlib import Path
import sys
import unicodedata
from difflib import SequenceMatcher

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from local_runtime import configure_local_runtime
configure_local_runtime()
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from faster_whisper import WhisperModel

WORK=ROOT/'cache/ezo_karaoke'
CLIPS=[(40,56),(80,96),(140,156),(220,236)]


def tokens(text):
    normalized=unicodedata.normalize('NFKD',text.casefold().replace('ı','i'))
    return [''.join(c for c in word if c.isalpha()) for word in normalized.split()
            if len(''.join(c for c in word if c.isalpha()))>=3]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('label');parser.add_argument('--scale',type=float,default=1.);parser.add_argument('--excerpt-start',type=float)
    args=parser.parse_args();WORK.mkdir(exist_ok=True)
    wave,rate=sf.read(args.source,dtype='float32',always_2d=True)
    model=WhisperModel(str(ROOT/'models/whisper/large-v3-turbo'),device='cpu',compute_type='int8',cpu_threads=4,num_workers=1)
    report={'label':args.label,'file':str(Path(args.source).resolve()),'diagnostic_only':True,
            'warning':'No recognized lyric match does not prove zero vocal leakage. Original isolated stems are unavailable.','clips':[]}
    clips=CLIPS if args.excerpt_start is None else [(args.excerpt_start,args.excerpt_start+len(wave)/rate)]
    for start,end in clips:
        clip=(wave[round(start*rate):round(end*rate)] if args.excerpt_start is None else wave).mean(axis=1)*args.scale
        audio=resample_poly(clip,16000,rate)
        segments,info=model.transcribe(audio,language='tr',beam_size=3,condition_on_previous_text=False,
            vad_filter=False,word_timestamps=True,temperature=0)
        rows=[{'start':float(s.start),'end':float(s.end),'text':s.text,'no_speech_prob':float(s.no_speech_prob),
               'avg_logprob':float(s.avg_logprob)} for s in segments]
        text=' '.join(row['text'] for row in rows)
        item={'start':start,'end':end,'segments':rows,'tokens':tokens(text)}
        reference=WORK/'asr_original.json'
        if reference.exists() and args.label!='original':
            expected=next(c for c in json.loads(reference.read_text(encoding='utf8'))['clips'] if c['start']==start)
            matcher=SequenceMatcher(None,expected['tokens'],item['tokens'],autojunk=False)
            item['matching_reference_token_count']=sum(block.size for block in matcher.get_matching_blocks())
            item['reference_token_count']=len(expected['tokens'])
            item['usable_lyric_reference']=len(expected['tokens'])>=3
        report['clips'].append(item)
        (WORK/f'asr_{args.label}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print(args.label,start,'recognized tokens',len(item['tokens']),'reference matches',item.get('matching_reference_token_count'),flush=True)


if __name__=='__main__':main()
