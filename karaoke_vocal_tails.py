"""Find held vocal endings on the stem, without extending into the next line."""
import copy
import math


def vocal_endpoint(levels,offset,step,start,end):
    import numpy as np
    if len(levels)<10 or not np.isfinite(levels).all():return None
    peak=float(np.max(levels))
    if peak<.003:return None
    threshold=max(.001,peak*.04,float(np.quantile(levels,.1))*3)
    active=levels>threshold
    # Bridge only short consonants inside a sung word, not a real breath/gap.
    first=None
    for i,on in enumerate([*active,True]):
        if not on and first is None:first=i
        if on and first is not None:
            if first>0 and i<len(active) and (i-first)*step<=.12:active[first:i]=True
            first=None
    runs=[];first=None
    for i,on in enumerate([*active,False]):
        if on and first is None:first=i
        if not on and first is not None:
            a,b=offset+first*step,offset+i*step
            if a<=start+.25 and b>=start+.35:
                runs.append((max(0,min(b,end)-max(a,start)),b,i))
            first=None
    if not runs:return None
    _,endpoint,index=max(runs)
    if len(levels)-index<round(.18/step):return None
    if np.any(active[index:index+round(.18/step)]):return None
    # An unvoiced consonant or brief within-word breath is not the end of a
    # word. Shorten only a genuinely quiet remainder of the original interval.
    old_end=min(len(active),max(index,math.ceil((end-offset)/step)))
    if endpoint<end and np.any(active[index:old_end]):return None
    return endpoint


def endpoint_support(word,endpoint,candidates):
    """Stereo energy alone also follows reverb. Require phonetic agreement."""
    from karaoke_ctc import acoustic_probability
    from karaoke_syllable_timing import text_key
    usable=[w for w in candidates if text_key(w.get('word',''))==text_key(word['word']) and
            acoustic_probability(w)>=.5 and isinstance(w.get('end'),(int,float)) and math.isfinite(w['end']) and abs(w['end']-endpoint)<=.16 and
            not w.get('needs_review') and w.get('model')]
    for i,a in enumerate(usable):
        for b in usable[i+1:]:
            if a['model']!=b['model']:return [a,b]
    return []


def recover_sustained_endings(audio_path,rows,endpoint_evidence=None):
    import numpy as np
    import soundfile as sf
    from karaoke_supplied_alignment import instrumental
    audio,rate=sf.read(str(audio_path),dtype='float32',always_2d=True)
    hop=max(1,round(rate*.02));step=hop/rate;duration=len(audio)/rate
    channels=[np.sqrt(np.mean(audio[:len(audio)//hop*hop,c].reshape(-1,hop).astype('float64')**2,axis=1))
              for c in range(min(2,audio.shape[1]))]
    report={'vocal_tail_repairs':[],'vocal_tail_review_candidates':[]}
    for ri,row in enumerate(rows):
        if row.get('locked') or instrumental(row) or not row.get('words'):continue
        word=row['words'][-1]
        if word.get('timing_source')=='manual' or not 0<=word['start']<word['end']:continue
        lower=max(0,word['start']-.1)
        upper=min(duration,rows[ri+1]['start'] if ri+1<len(rows) else duration,word['end']+1.8)
        if upper-lower<.5:continue
        a,b=int(lower/step),min(len(channels[0]),int(upper/step))
        endpoints=[vocal_endpoint(c[a:b],a*step,step,word['start'],word['end']) for c in channels]
        if len(endpoints)<2 or any(e is None for e in endpoints) or max(endpoints)-min(endpoints)>.06:continue
        endpoint=float(np.mean(endpoints))
        if abs(endpoint-word['end'])<.12 or endpoint<=word['start'] or endpoint>=upper-.16:continue
        old=word['end']
        key=(row.get('id') or f'row:{ri+1}',len(row['words'])-1)
        candidates=list((endpoint_evidence or {}).get(key,[]))
        candidates.extend((word.get('alignment_audit') or {}).get('evidence') or [])
        reference=word.get('timing_reference') or {}
        if reference.get('method') in ('bounded_multimodel_ctc','phrase_multimodel_consensus') and reference.get('acoustically_verified'):
            candidates.extend(reference.get('evidence') or [])
        support=endpoint_support(word,endpoint,candidates)
        if not support:
            # Energy alone must not overrule two models corroborating the
            # existing endpoint. Retain any prior review flag; never clear it.
            confirmed_current=endpoint_support(word,old,candidates)
            if not confirmed_current:word['needs_review']=True
            report['vocal_tail_review_candidates'].append({'row':ri+1,'word':word['word'],'current_end':old,
                'candidate_end':endpoint,'reason':('phonetic_endpoint_preserved_unconfirmed_energy_tail'
                    if confirmed_current else 'energy_can_include_reverb_not_independently_verified')})
            continue
        # This verifies the vocal endpoint only. Keep lexical review flags until
        # a recognizer or independent phrase evidence also verifies the word.
        word['end']=endpoint
        word['timing_reference']={'method':'vocal_sustain_endpoint','scope':'end_only',
            'previous_start':word['start'],'previous_end':old,'channel_endpoints':endpoints,
            'endpoint_evidence':copy.deepcopy(support),
            'previous_reference':copy.deepcopy(word.get('timing_reference'))}
        row['end']=endpoint
        report['vocal_tail_repairs'].append({'row':ri+1,'word':word['word'],'before':old,'after':endpoint})
    return report
