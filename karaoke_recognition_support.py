"""Require independent recognized text before accepting weaker forced timings."""
import copy
import math

from karaoke_ctc import acoustic_probability, has_timed_row
from karaoke_repeat_inference import token_key


def supported_word(original,candidates,observations,lower,upper):
    """Recognition supplies lexical evidence; CTC supplies bounded phoneme times."""
    key=token_key(original['word'])
    recognized=[w for w in observations if token_key(w['word'])==key and acoustic_probability(w)>=.65
                and w['end']>w['start'] and not w.get('rejected')]
    # Whisper word timestamps are coarse in singing. Agreement is lexical
    # evidence only; it must not overwrite phonetic timings on its own.
    usable=[w for w in candidates if w['word']==original['word'] and acoustic_probability(w)>=.25
            and lower<=w['start']<w['end']<=upper and w['end']-w['start']<=3.5]
    pairs=[]
    for i,a in enumerate(usable):
        for b in usable[i+1:]:
            if (a['model'],a['source'],a['channel'])==(b['model'],b['source'],b['channel']):continue
            if max(abs(a[k]-b[k]) for k in ('start','end'))>.16:continue
            start,end=(a['start']+b['start'])/2,(a['end']+b['end'])/2
            lexical=[w for w in recognized if abs(w['start']-start)<=.65 and abs(w['end']-end)<=.85
                     and min(end,w['end'])-max(start,w['start'])>=.5*(end-start)]
            independent={w['model'] for w in lexical}
            # A single recognition is sufficient only with two different CTC
            # models, each with appreciable phonetic evidence. Never accept
            # repeated contexts from the same model as independent evidence.
            single_strong=lexical and max(acoustic_probability(w) for w in lexical)>=.9
            threshold=.3 if single_strong else .4
            if len(independent)<2 and not (lexical and a['model']!=b['model']
                    and min(acoustic_probability(a),acoustic_probability(b))>=threshold):continue
            pairs.append((a,b,lexical))
    if not pairs:return original
    a,b,lexical=max(pairs,key=lambda p:min(acoustic_probability(w) for w in p[:2]))
    return {**original,'start':(a['start']+b['start'])/2,'end':(a['end']+b['end'])/2,
        'timing_source':'ctc','probability':min(acoustic_probability(a),acoustic_probability(b)),
        'needs_review':False,'timing_reference':{'method':'recognition_supported_ctc_consensus',
            'acoustically_verified':True,'previous_start':original['start'],'previous_end':original['end'],
            'phonetic_evidence':[copy.deepcopy(a),copy.deepcopy(b)],'lexical_evidence':copy.deepcopy(lexical)}}


def apply_recognition_support(rows,candidates,observations,duration):
    repaired=[]
    for ri,row in enumerate(rows):
        if row.get('locked'):continue
        for wi,word in enumerate(row.get('words') or []):
            if not word.get('needs_review') or word.get('timing_source')=='manual':continue
            lower=max([0.]+[r['end'] for r in rows[:ri] if has_timed_row(r)]+
                      [w['end'] for w in row['words'][:wi] if w['end']>w['start']])
            upper=min([duration]+[r['start'] for r in rows[ri+1:] if has_timed_row(r)]+
                      [w['start'] for w in row['words'][wi+1:] if w['end']>w['start']])
            fixed=supported_word(word,candidates.get((ri,wi),[]),observations,lower,upper)
            if fixed is not word:row['words'][wi]=fixed;repaired.append((ri+1,word['word']))
        good=[w for w in row.get('words') or [] if w['end']>w['start']]
        if good:row['start']=min(w['start'] for w in good);row['end']=max(w['end'] for w in good)
    return repaired


def review_windows(rows,duration,limit=12):
    """Bound work and never search an entire song for an unlocated syllable."""
    windows=[];skipped=0
    for ri,row in enumerate(rows):
        if row.get('locked') or not any(w.get('needs_review') and w.get('timing_source')!='manual' for w in row.get('words') or []):continue
        lower=max([0.]+[r['end'] for r in rows[:ri] if has_timed_row(r)])
        upper=min([duration]+[r['start'] for r in rows[ri+1:] if has_timed_row(r)])
        valid=[w for w in row.get('words') or [] if w['end']>w['start']]
        a=max(lower,min((w['start'] for w in valid),default=lower)-.8)
        b=min(upper,max((w['end'] for w in valid),default=upper)+.8)
        if not .2<b-a<=35 or (limit is not None and len(windows)>=limit):skipped+=1;continue
        if windows and a<=windows[-1][1] and b-windows[-1][0]<=35:
            windows[-1]=(windows[-1][0],max(b,windows[-1][1]))
        else:windows.append((a,b))
    return windows,skipped


def recover_recognition_reviews(vocal_path,original_path,rows,model_loader,diagnostics,progress,language):
    """Retry uncertain phrases without a lyric prompt, using installed models.

    This is corroboration, not a substitute for acoustic timing or a guarantee.
    No model download, unconstrained search, or removal of supplied words.
    """
    from pathlib import Path
    import soundfile as sf
    report={'recognition_repaired_words':0,'recognition_windows':0,'recognition_skipped_windows':0}
    info=sf.info(str(vocal_path));duration=info.duration
    windows,report['recognition_skipped_windows']=review_windows(rows,duration,limit=None)
    if not windows:return report
    from faster_whisper.tokenizer import _LANGUAGE_CODES
    if language not in _LANGUAGE_CODES:
        report['recognition_skipped_reason']='whisper_language_not_supported'
        return report
    directory=Path(__file__).resolve().parent/'models/whisper'
    models=[name for name in ('large-v3','large-v3-turbo') if (directory/name/'model.bin').is_file()]
    if not models:
        report['recognition_skipped_reason']='no_installed_model';return report
    candidates={}
    indices={row.get('id') or f'row:{ri+1}':ri for ri,row in enumerate(rows)}
    for entry in diagnostics.get('model_crosscheck_candidates',[]):
        ri=indices.get(entry['row_id'])
        if ri is not None:
            candidates.setdefault((ri,entry['word_index']),[]).extend({**w,'source':w['audio_source']} for w in entry['candidates'])
    sources=[('vocals',vocal_path)]
    if original_path and Path(original_path).is_file() and abs(sf.info(str(original_path)).duration-duration)<=.05:
        sources.append(('original',original_path))
    import torch
    import torchaudio.functional as AF
    from karaoke_supplied_alignment import alignment_mono
    observations=[]
    for model_name in models:
        model=model_loader(model_name)
        for source,path in sources:
            for a,b in windows:
                progress(.99,f'Belirsiz sözler ikinci kez dinleniyor · {model_name} · {source} · {a:.1f}–{b:.1f} sn')
                try:
                    meta=sf.info(str(path))
                    audio,rate=sf.read(str(path),start=round(a*meta.samplerate),stop=round(b*meta.samplerate),dtype='float32',always_2d=True)
                    mono=alignment_mono(audio)
                    if rate!=16000:mono=AF.resample(torch.from_numpy(mono.copy()),rate,16000).numpy()
                    decoded,_=model.transcribe(mono,language=language,
                        beam_size=5,word_timestamps=True,condition_on_previous_text=False,vad_filter=True)
                    for segment in decoded:
                        for word in segment.words or []:
                            observations.append({'word':word.word.strip(),'start':a+word.start,'end':a+word.end,
                                'probability':word.probability,'model':model_name,'source':source})
                    report['recognition_windows']+=1
                except Exception as exc:
                    report.setdefault('recognition_errors',[]).append({'model':model_name,'source':source,'reason':str(exc)})
        repaired=apply_recognition_support(rows,candidates,observations,duration)
        report['recognition_repaired_words']+=len(repaired)
        if not any(w.get('needs_review') and w.get('timing_source')!='manual' for r in rows if not r.get('locked') for w in r.get('words') or []):break
    return report
