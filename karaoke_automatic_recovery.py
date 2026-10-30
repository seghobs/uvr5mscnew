"""Bounded automatic retries and measured repeat support for supplied lyrics.

No song names/positions, fabricated confidence, text edits, or inferred timing
as acoustic evidence. Every optional repair retains its witnesses.
"""
import copy
import math
import re
import statistics
from pathlib import Path

from karaoke_ctc import acoustic_probability
from karaoke_repeat_inference import token_key


def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def located(word):
    return all(finite(word.get(k)) for k in ('start','end')) and 0<=word['start']<word['end']


def acoustic_content(path,start,end,rate):
    import numpy as np
    import soundfile as sf
    clip,_=sf.read(str(path),start=max(0,round(start*rate)),stop=round(end*rate),
                   dtype='float32',always_2d=True)
    return bool(clip.size and np.isfinite(clip).all() and np.sqrt(np.mean(clip.astype('float64')**2))>1e-5
                and np.max(np.std(clip,axis=0))>1e-5)


def key(row,index):return row.get('id') or f'row:{index+1}'


def targets(rows):
    result=[]
    from karaoke_supplied_alignment import instrumental
    from karaoke_syllable_timing import syllable_pieces
    for ri,row in enumerate(rows):
        if row.get('locked') or instrumental(row):continue
        for wi,word in enumerate(row.get('words') or []):
            if word.get('timing_source')=='manual':continue
            current_parts=bool(word.get('timing_parts') and syllable_pieces(word))
            if (word.get('needs_review') or not located(word)
                    or word.get('timing_source') in ('estimated','repeat_inferred')
                    or re.search(r'[,;،][^\W\d_]',word['word']) and not current_parts
                    or word['end']-word['start']>6 and not current_parts):
                result.append((ri,wi))
    return result


def bounds(rows,ri,wi,duration):
    before=[w['end'] for r in rows[:ri] for w in r.get('words') or [] if located(w)]
    after=[w['start'] for r in rows[ri+1:] for w in r.get('words') or [] if located(w)]
    before.extend(w['end'] for w in rows[ri].get('words',[])[:wi] if located(w))
    after.extend(w['start'] for w in rows[ri].get('words',[])[wi+1:] if located(w))
    return max([0.]+before),min([duration]+after)


def strict_vote(proposals,word,lower,upper):
    """One vote per model/source, and no arbitrary choice between equal clusters."""
    usable=[p for p in proposals if p.get('model') and p.get('source') and located(p)
            and token_key(p.get('word',''))==token_key(word['word']) and acoustic_probability(p)>=.5
            and not p.get('needs_review') and lower<=p['start']<p['end']<=upper]
    groups=[]
    for anchor in usable:
        unique={}
        for p in usable:
            if any(abs(p[k]-anchor[k])>.12 for k in ('start','end')):continue
            identity=(p['model'],p['source'])
            if identity not in unique or acoustic_probability(p)>acoustic_probability(unique[identity]):unique[identity]=p
        group=list(unique.values());models={p['model'] for p in group}
        if len(models)<2 or any(max(p[k] for p in group)-min(p[k] for p in group)>.16 for k in ('start','end')):continue
        rank=(len(models),len(group),min(acoustic_probability(p) for p in group))
        groups.append((rank,group))
    if not groups:return None
    rank,best=max(groups,key=lambda entry:entry[0])
    a,b=(statistics.median(p[k] for p in best) for k in ('start','end'))
    for other_rank,group in groups:
        if other_rank[:2]==rank[:2] and any(abs(statistics.median(p[k] for p in group)-value)>.16
                for k,value in (('start',a),('end',b))):return None
    result={**copy.deepcopy(word),'start':a,'end':b,'probability':rank[2],
            'timing_source':'ctc','needs_review':False,'timing_reference':{
                'method':'bounded_multimodel_ctc','acoustically_verified':True,
                'previous_start':word.get('start'),'previous_end':word.get('end'),'evidence':copy.deepcopy(best)}}
    for field in ('syllables','syllable_reference','timing_parts','timing_parts_reference','alignment_audit'):result.pop(field,None)
    parts=[p for p in best if p.get('pieces')]
    if parts:
        count=len(parts[0]['pieces'])
        parts=[p for p in parts if len(p['pieces'])==count]
        if len({p['model'] for p in parts})<2:return None
        measured=[];previous=a
        for index in range(count):
            pieces=[p['pieces'][index] for p in parts]
            if len({token_key(p['text']) for p in pieces})!=1:return None
            if any(max(p[k] for p in pieces)-min(p[k] for p in pieces)>.12 for k in ('start','end')):return None
            start,end=(statistics.median(p[k] for p in pieces) for k in ('start','end'))
            score=min(p['score'] for p in pieces)
            if score<.5 or not a<=previous<=start<end<=b:return None
            measured.append({'text':pieces[0]['text'],'start':start,'end':end,'score':score});previous=end
        result['timing_parts']=measured
        result['timing_parts_reference']={'word_text':word['word'],'word_start':a,'word_end':b}
    return result


def alignment_input(row):
    """Expand punctuation only in the model input; retain exact editor tokens."""
    item=copy.deepcopy(row);words=[];layout=[]
    for wi,word in enumerate(row.get('words') or []):
        pieces=re.split(r'(?<=[,;،])(?=[^\W\d_])',word['word'])
        for text in pieces:words.append({**word,'word':text});layout.append(wi)
    item['words']=words;item['text']=' '.join(w['word'] for w in words)
    item['_recovery_layout']=layout
    return item


def collect_pass(path,source,rows,indices,model,padding,channel,session,evidence,progress):
    from karaoke_ctc import refine_ctc
    from karaoke_alignment_models import model_spec
    selected=[]
    for ri in indices:
        row=alignment_input(rows[ri]);row['_recovery_index']=ri;selected.append(row)
    proposed=refine_ctc(str(path),selected,model,context_padding=padding,channel=channel,
                        independent_rows=True,session=session,progress=lambda _p,m:progress(.995,m))
    model_id=model_spec(model)[1]
    for row in proposed:
        ri=row['_recovery_index'];layout=row['_recovery_layout'];words=row.get('words') or []
        if len(words)!=len(layout):continue
        for wi,original in enumerate(rows[ri].get('words') or []):
            pieces=[w for w,index in zip(words,layout) if index==wi]
            if not pieces:continue
            p={**copy.deepcopy(pieces[0]),'word':original['word'],'end':pieces[-1]['end'],
                'probability':min(acoustic_probability(w) for w in pieces),
                'needs_review':any(w.get('needs_review') for w in pieces),
                'model':model_id,'source':source,'channel':channel,'context_padding':padding}
            if len(pieces)>1:p['pieces']=[{'text':w['word'],'start':w['start'],'end':w['end'],
                'score':acoustic_probability(w)} for w in pieces]
            evidence.setdefault((key(rows[ri],ri),wi),[]).append(p)


def installed(model):
    from karaoke_alignment_models import model_spec,MMS_ADAPTERS
    folder,_,_=model_spec(model)
    files=['config.json','preprocessor_config.json','vocab.json']
    if model in MMS_ADAPTERS:files.append('adapter.'+MMS_ADAPTERS[model]+'.safetensors')
    return any((folder/name).is_file() for name in ('pytorch_model.bin','model.safetensors')) and all(
        (folder/name).is_file() for name in files)


def proven(word,proposals):
    if not located(word) or word.get('needs_review') or word.get('timing_source') in ('estimated','repeat_inferred'):return False
    if word.get('timing_source')=='manual':return True
    vote=strict_vote(proposals,word,0.,math.inf)
    return bool(vote and all(abs(vote[k]-word[k])<=.16 for k in ('start','end')))


class AcousticMatcher:
    """Read bounded clips lazily; no splicing of silence, and finite DTW only."""
    def __init__(self,path,progress,budget=20000):
        import soundfile as sf
        self.path=path;self.info=sf.info(str(path));self.cache={};self.calls=0
        self.budget=budget;self.progress=progress

    def feature(self,start,end,phrase=False):
        import numpy as np
        import soundfile as sf
        import librosa
        from karaoke_supplied_alignment import alignment_mono
        from karaoke_review_recovery import repeat_features
        a=max(0,start-(.15 if phrase else .06));b=min(self.info.duration,end+(.9 if phrase else .06))
        if not all(finite(t) for t in (a,b)) or not .025<=b-a<=20:return None
        cache_key=(a,b,phrase)
        if cache_key in self.cache:return self.cache[cache_key]
        clip,rate=sf.read(str(self.path),start=round(a*self.info.samplerate),stop=round(b*self.info.samplerate),
                          dtype='float32',always_2d=True)
        if not phrase:features=repeat_features(clip,rate)
        else:
            wave=librosa.resample(alignment_mono(clip),orig_sr=rate,target_sr=16000)
            if len(wave)<400 or not np.isfinite(wave).all() or float(np.sqrt(np.mean(wave**2)))<1e-5:return None
            mfcc=librosa.feature.mfcc(y=wave,sr=16000,n_mfcc=16,n_fft=400,hop_length=160)[2:]
            norm=np.linalg.norm(mfcc,axis=0,keepdims=True);active=norm>1e-8
            if not np.isfinite(mfcc).all() or not np.any(active):return None
            features=np.vstack((np.divide(mfcc,norm,out=np.zeros_like(mfcc),where=active),(~active).astype(mfcc.dtype)))
        result=None if features is None else (features,a)
        if len(self.cache)>=512:self.cache.pop(next(iter(self.cache)))
        self.cache[cache_key]=result
        return result

    def distance(self,a,b,phrase=False,path=False):
        import librosa
        if self.calls>=self.budget:return None
        self.calls+=1
        if self.calls%50==1:self.progress(.995,'Şüpheli kelimeler ve nakaratlar sesle karşılaştırılıyor…')
        first=self.feature(a['start'],a['end'],phrase);second=self.feature(b['start'],b['end'],phrase)
        if first is None or second is None:return None
        try:
            matrix,alignment=librosa.sequence.dtw(X=first[0],Y=second[0],metric='cosine',
                **({'global_constraints':True,'band_rad':.12} if phrase else {}))
            cost=float(matrix[-1,-1]/len(alignment))
            if not finite(cost) or cost<0:return None
            return (cost,alignment,first[1],second[1]) if path else cost
        except (ValueError,FloatingPointError):return None


def contrast(matcher,target,references,phrase=False):
    if matcher.calls>=matcher.budget:return None
    positives=[];negatives=[]
    for ref in references:
        if abs(ref['start']-target['start'])<1:continue
        ratio=(ref['end']-ref['start'])/(target['end']-target['start'])
        if not (.6<=ratio<=1.6 if phrase else .35<=ratio<=3.):continue
        cost=matcher.distance(target,ref,phrase)
        if cost is None:continue
        (positives if ref['label']==target['label'] else negatives).append((cost,ref))
    if matcher.calls>=matcher.budget or not positives or not negatives:return None
    positive,reference=min(positives,key=lambda x:x[0]);negative=min(c for c,_ in negatives)
    if not (positive<.2 and positive<negative*.75):return None
    return {'same_distance':positive,'negative_distance':negative,'reference':reference}


def word_references(rows,verified):
    return [{**copy.deepcopy(w),'label':token_key(w['word']),'row_id':key(r,ri),'word_index':wi}
        for ri,r in enumerate(rows) for wi,w in enumerate(r.get('words') or []) if (ri,wi) in verified]


def repeat_repair(word,proposals,lower,upper,matcher,references):
    from karaoke_review_recovery import repeat_boundary_candidate
    candidates=[{**p,'recovery_channel':':'.join(str(p.get(k,'')) for k in ('model','source','channel'))}
                for p in proposals if located(p) and acoustic_probability(p)>=.3
                and token_key(p.get('word',''))==token_key(word['word'])]
    if located(word) and word.get('timing_source')=='ctc' and acoustic_probability(word)>=.3:
        candidates.append({**word,'model':'stored_ctc','source':'vocals','recovery_channel':'stored_ctc'})
    seeds=[word] if located(word) else [p for p in candidates if lower<=p['start']<p['end']<=upper]
    seen=set()
    for seed in seeds:
        identity=(round(seed['start'],2),round(seed['end'],2))
        if identity in seen:continue
        seen.add(identity)
        proof=contrast(matcher,{**seed,'label':token_key(word['word'])},references)
        if proof is None:continue
        chosen=repeat_boundary_candidate(seed,candidates,lower,upper,proof['same_distance'],proof['negative_distance'])
        if chosen is seed:continue
        after=contrast(matcher,{**chosen,'label':token_key(word['word'])},references)
        if after is None:continue # a new interval needs its own acoustic test
        evidence=[p for p in candidates if all(abs(p[k]-chosen[k])<=.04 for k in ('start','end'))]
        chosen={**copy.deepcopy(word),**{k:chosen[k] for k in ('start','end','probability','timing_source','needs_review')}}
        for field in ('syllables','syllable_reference','timing_parts','timing_parts_reference','alignment_audit'):chosen.pop(field,None)
        chosen['timing_reference']={'method':'acoustic_repeat_supported_ctc','acoustically_verified':True,
            'previous_start':word.get('start'),'previous_end':word.get('end'),
            'same_distance':after['same_distance'],'negative_distance':after['negative_distance'],
            'reference_row_id':after['reference']['row_id'],'reference_word_index':after['reference']['word_index'],
            'evidence':copy.deepcopy(evidence)}
        return chosen
    return None


def consistent_warps(matches,tolerance=.04):
    """Use agreement across repetitions, not just the two nearest spectra."""
    groups=[]
    for anchor in matches:
        group=[m for m in matches if all(abs(m[k]-anchor[k])<=tolerance+1e-7 for k in ('start','end'))]
        unique={m['row_id']:m for m in group};group=list(unique.values())
        if any(max(m[k] for m in group)-min(m[k] for m in group)>tolerance+1e-7 for k in ('start','end')):continue
        groups.append(group)
    if not groups:return []
    best=max(groups,key=lambda g:(len(g),-statistics.mean(m['cost'] for m in g)))
    for group in groups:
        if len(group)==len(best) and any(abs(statistics.median(m[k] for m in group)-
                statistics.median(m[k] for m in best))>tolerance+1e-7 for k in ('start','end')):return []
    return best


def phrase_repair(rows,ri,wi,verified,matcher,proposals,lower,upper):
    import numpy as np
    row=rows[ri];word=row['words'][wi]
    # Parent boundaries alone cannot certify an interior punctuation breath.
    # Such tokens require the measured component consensus in strict_vote.
    if re.search(r'[,;،][^\W\d_]',word['word']):return None
    if not located(word) or not 2<=len(row['words'])<=8 or not 0<row['end']-row['start']<=18:return None
    references=[];count=len(row['words']);label=tuple(token_key(w['word']) for w in row['words'])
    for rj,other in enumerate(rows):
        if rj==ri:continue
        words=other.get('words') or []
        for first in range(len(words)-count+1):
            if not all((rj,j) in verified for j in range(first,first+count)):continue
            group=words[first:first+count]
            references.append({'start':group[0]['start'],'end':group[-1]['end'],
                'label':tuple(token_key(w['word']) for w in group),'words':group,'row_id':key(other,rj)})
    target={'start':row['start'],'end':row['end'],'label':label}
    proof=contrast(matcher,target,references,True)
    if proof is None:return None
    matches=[]
    for ref in references:
        if ref['label']!=label:continue
        measured=matcher.distance(target,ref,True,True)
        if measured is None or measured[0]>=.2:continue
        cost,path,a,b=measured;point={}
        for edge in ('start','end'):
            frame=round((ref['words'][wi][edge]-b)/.01)
            frames=path[np.abs(path[:,1]-frame)<=1,0]
            if not len(frames):break
            point[edge]=float(a+np.median(frames)*.01)
        if len(point)==2:matches.append({**point,'cost':cost,'row_id':ref['row_id']})
    if not matches:return None
    best=consistent_warps(matches)
    if not best:return None
    a,b=(statistics.median(p[k] for p in best) for k in ('start','end'))
    witnesses=[p for p in proposals if located(p) and acoustic_probability(p)>=.3
               and token_key(p.get('word',''))==token_key(word['word'])
               and abs(p['start']-a)<=.12 and abs(p['end']-b)<=.16]
    stored_witness=(word.get('timing_source')=='ctc' and acoustic_probability(word)>=.3
        and (word.get('timing_reference') or {}).get('method') in (None,'bounded_multimodel_ctc',
            'joint_row_boundary_consensus','language_model_alignment','language_model_channel_consensus')
        and abs(word['start']-a)<=.12 and abs(word['end']-b)<=.16)
    if stored_witness:
        witnesses.append(word)
    if not witnesses or not lower<=a<b<=upper:return None
    # One strong reference can suffice only with two separate CTC observations.
    identities={(p.get('model'),p.get('source'),p.get('channel')) for p in witnesses if p.get('model')}
    if stored_witness:identities.add(('stored_ctc','existing_measurement','existing'))
    if len(best)==1 and len(identities)<2:return None
    chosen={**copy.deepcopy(word),'start':a,'end':b,'timing_source':'ctc','needs_review':False,
        'timing_reference':{'method':'phrase_contrast_and_dtw_boundary','acoustically_verified':True,
            'previous_start':word['start'],'previous_end':word['end'],'same_phrase_cost':proof['same_distance'],
            'negative_phrase_cost':proof['negative_distance'],'warped_references':best,'evidence':copy.deepcopy(witnesses)}}
    for field in ('syllables','syllable_reference','timing_parts','timing_parts_reference','alignment_audit'):chosen.pop(field,None)
    return chosen


def recover_automatic_alignment(vocal_path,original_path,rows,progress=lambda *args:None,language='tr',evidence=None):
    import soundfile as sf
    from karaoke_inference import RefinementSession
    from karaoke_supplied_alignment import instrumental,protected
    report={'automatic_recovery_enabled':True,'automatic_recovery_strict_words':0,
        'automatic_recovery_repeat_words':0,'automatic_recovery_phrase_words':0,
        'automatic_recovery_errors':[],'automatic_recovery_skipped_models':[]}
    initial=targets(rows);report['automatic_recovery_initial_words']=len(initial)
    if not initial:
        report.update(automatic_recovery_remaining_words=0,automatic_recovery_verified_keys=[]);return report
    info=sf.info(str(vocal_path));duration=info.duration;frozen=copy.deepcopy(rows);signal_cache={}
    def has_sound(word):
        span=(word['start'],word['end'])
        if span not in signal_cache:signal_cache[span]=acoustic_content(vocal_path,*span,info.samplerate)
        return signal_cache[span]
    pooled=copy.deepcopy(evidence or {});sources=[('vocals',vocal_path)]
    if original_path and Path(original_path).is_file() and abs(sf.info(str(original_path)).duration-duration)<=.05:
        sources.append(('original',original_path))
    models={'tr':('tr','tr_mms','tr_cv8'),'kmr':('kmr_mms','kmr','tr','tr_cv8'),
            'en':('en_lv60','en'),'az':('az',)}.get(language,())
    eligible=[i for i,r in enumerate(frozen) if not protected(r) and not instrumental(r)
              and located(r) and r['end']-r['start']<=18 and r.get('words')]
    for ri,wi in initial:rows[ri]['words'][wi]['needs_review']=True
    def apply_strict():
        accepted=set()
        for ri,wi in initial:
            original=frozen[ri]['words'][wi];a,b=bounds(rows,ri,wi,duration)
            chosen=strict_vote(pooled.get((key(frozen[ri],ri),wi),[]),original,a,b)
            if chosen and has_sound(chosen) and (not located(original) or abs(chosen['start']-original['start'])<=.8):
                rows[ri]['words'][wi]=chosen;accepted.add((ri,wi))
            else:
                rows[ri]['words'][wi]=copy.deepcopy(original);rows[ri]['words'][wi]['needs_review']=True
        return accepted
    accepted=apply_strict()
    with RefinementSession() as session:
        for model in models:
            if not installed(model):report['automatic_recovery_skipped_models'].append(model);continue
            if len(accepted)==len(initial):break
            for source,path in sources:
                for padding,channel in ((.35,'mix'),(.9,'mix'),(.25,'left'),(.25,'right'),(1.2,'left'),(1.2,'right')):
                    pending={ri for ri,wi in initial if (ri,wi) not in accepted}
                    if not pending:break
                    # The first pass also measures reference phrases. Later
                    # retries concentrate on unresolved rows, with no row cap.
                    indices=eligible if padding==.35 and channel=='mix' else [i for i in eligible if i in pending]
                    progress(.995,f'Otomatik ek kontrol · {model} · {source} · {channel}')
                    try:collect_pass(path,source,frozen,indices,model,padding,channel,session,pooled,progress)
                    except Exception as exc:
                        report['automatic_recovery_errors'].append({'model':model,'source':source,'reason':str(exc)});break
                    accepted=apply_strict()
    report['automatic_recovery_strict_words']=len(accepted)
    for r in rows:
        good=[w for w in r.get('words') or [] if located(w)]
        if good and not protected(r) and not instrumental(r):r['start']=good[0]['start'];r['end']=good[-1]['end']
    verified={(ri,wi) for ri,r in enumerate(rows) if not instrumental(r) for wi,w in enumerate(r.get('words') or [])
              if proven(w,pooled.get((key(r,ri),wi),[])) and (w.get('timing_source')=='manual' or has_sound(w))}
    verified|=accepted
    references=word_references(copy.deepcopy(rows),verified);matcher=AcousticMatcher(vocal_path,progress)
    for ri,wi in initial:
        if (ri,wi) in accepted:continue
        r=rows[ri];a,b=bounds(rows,ri,wi,duration)
        chosen=repeat_repair(r['words'][wi],pooled.get((key(r,ri),wi),[]),a,b,matcher,references)
        if chosen:
            r['words'][wi]=chosen;verified.add((ri,wi));report['automatic_recovery_repeat_words']+=1
    # Freeze measured word-level repairs before phrase-level use: no circular
    # references and no phrase repair becomes evidence for another phrase.
    phrase_rows=copy.deepcopy(rows);phrase_verified=set(verified)
    for r in phrase_rows:
        good=[w for w in r.get('words') or [] if located(w)]
        if good and not protected(r) and not instrumental(r):r['start']=good[0]['start'];r['end']=good[-1]['end']
    for ri,wi in initial:
        if (ri,wi) in verified:continue
        a,b=bounds(rows,ri,wi,duration)
        chosen=phrase_repair(phrase_rows,ri,wi,phrase_verified,matcher,pooled.get((key(rows[ri],ri),wi),[]),a,b)
        if chosen:
            rows[ri]['words'][wi]=chosen;verified.add((ri,wi));report['automatic_recovery_phrase_words']+=1
    for r in rows:
        good=[w for w in r.get('words') or [] if located(w)]
        if good and not protected(r) and not instrumental(r):r['start']=good[0]['start'];r['end']=good[-1]['end']
    if evidence is not None:
        evidence.clear();evidence.update(pooled)
    report.update(automatic_recovery_remaining_words=sum(bool(rows[ri]['words'][wi].get('needs_review')) for ri,wi in initial),
        automatic_recovery_pending_keys=[[key(rows[ri],ri),wi] for ri,wi in initial if rows[ri]['words'][wi].get('needs_review')],
        automatic_recovery_verified_keys=[[key(rows[ri],ri),wi] for ri,wi in sorted(verified)
            if not rows[ri].get('locked') and rows[ri]['words'][wi].get('timing_source')!='manual'],
        automatic_recovery_acoustic_comparisons=matcher.calls,
        automatic_recovery_comparison_budget_exhausted=matcher.calls>=matcher.budget)
    return report
