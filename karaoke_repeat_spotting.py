"""Find occurrences of supplied text in CTC evidence before global alignment."""
import numpy as np
from numba import njit

@njit(cache=True)
def phrase_paths(emission,targets,blank=0):
    states=np.zeros(2*len(targets)+1,np.int32)
    for i in range(len(targets)):states[2*i+1]=targets[i]
    score=np.full(len(states),-1e20);starts=np.zeros(len(states),np.int32)
    score[0]=0
    output=np.empty(len(emission));begins=np.empty(len(emission),np.int32)
    for t in range(len(emission)):
        new=np.full(len(states),-1e20);newstarts=starts.copy();new[0]=0;newstarts[0]=t
        maximum=np.max(emission[t])
        for j in range(1,len(states)):
            best=score[j];previous=j
            if score[j-1]>best:best=score[j-1];previous=j-1
            if j>1 and states[j]!=blank and states[j]!=states[j-2] and score[j-2]>best:
                best=score[j-2];previous=j-2
            new[j]=best+emission[t,states[j]]-maximum-.01
            newstarts[j]=t if previous==0 else starts[previous]
        score=new;starts=newstarts
        output[t]=score[-2]/max(1,len(targets));begins[t]=starts[-2]
    return output,begins

def find_occurrences(emission,row,vocab,threshold=-3.0,rescue=None,progress=lambda *args:None):
    import torch
    import torchaudio.functional as AF
    from scipy.signal import find_peaks
    from karaoke_ctc import normalized_words,words_from_spans
    from karaoke_supplied_alignment import spoken
    words=[{'word':t} for t in row['text'].split() if spoken(t)]
    try:normalized=normalized_words(words,vocab)
    except ValueError:return []
    targets=np.asarray([vocab[c] for c in '|'.join(normalized)],np.int32)
    if len(targets)<5:return []
    scores,starts=phrase_paths(emission,targets,vocab.get('[PAD]',0))
    peaks,_=find_peaks(scores,height=threshold,distance=25)
    proposals=[]
    ordered=sorted(peaks,key=lambda t:scores[t],reverse=True)
    for candidate_index,end in enumerate(ordered):
        progress(candidate_index/max(1,len(ordered)),f'Tekrar adayı {candidate_index+1}/{len(ordered)} · {end*.02:.2f} sn')
        start=int(starts[end]);a=max(0,start);b=min(len(emission),int(end)+1)
        if (end-start)<len(targets)*.9 or end-start>max(300,len(targets)*40):continue
        try:
            clip=torch.from_numpy(emission[a:b].copy())[None]
            path,prob=AF.forced_align(clip,torch.from_numpy(targets[None]),blank=vocab.get('[PAD]',0))
            spans=AF.merge_tokens(path[0],prob[0].exp(),blank=vocab.get('[PAD]',0))
            aligned=words_from_spans(words,normalized,spans,targets.tolist(),.02,a*.02)
        except (ValueError,RuntimeError):continue
        # A short interjection must not borrow its first vowel from the preceding line.
        if len(normalized[0])<=2 and len(aligned)>=4 and aligned[0]['end']-aligned[0]['start']>1.2:
            trimmed=max(a,round((aligned[1]['start']-1.2)*50))
            if trimmed>a:
                try:
                    clip=torch.from_numpy(emission[trimmed:b].copy())[None]
                    path,prob=AF.forced_align(clip,torch.from_numpy(targets[None]),blank=vocab.get('[PAD]',0))
                    spans=AF.merge_tokens(path[0],prob[0].exp(),blank=vocab.get('[PAD]',0))
                    alternative=words_from_spans(words,normalized,spans,targets.tolist(),.02,trimmed*.02)
                    if alternative[0]['probability']>=.1:
                        aligned=alternative;start=round(aligned[0]['start']*50)
                except (ValueError,RuntimeError):pass
        from difflib import SequenceMatcher
        labels=emission[round(aligned[0]['start']*50):round(aligned[-1]['end']*50)].argmax(axis=1)
        inverse={value:key for key,value in vocab.items()}
        decoded=''.join(inverse[t] for i,t in enumerate(labels) if t not in (vocab.get('[PAD]',0),vocab['|']) and (i==0 or labels[i-1]!=t))
        similarity=SequenceMatcher(None,''.join(normalized),decoded).ratio()
        if similarity<.5:continue
        confidence=sum(w['probability'] for w in aligned)/len(aligned)
        if confidence<.4 or min(w['probability'] for w in aligned)<.1:
            # Borderline whole-song scores can improve on a bounded audio clip.
            # The independently re-inferred result must still pass the original
            # .4 mean/.1 minimum thresholds below; never accept a weak guess.
            if rescue is None or confidence<.3:continue
            alternative=rescue(row,aligned[0]['start'],aligned[-1]['end'])
            if not alternative:continue
            aligned=alternative;confidence=sum(w['probability'] for w in aligned)/len(aligned)
            if confidence<.4 or min(w['probability'] for w in aligned)<.1:continue
        if max(w['end']-w['start'] for w in aligned)>6:continue
        if any(y['start']-x['end']>3 for x,y in zip(aligned,aligned[1:])):continue
        proposals.append({'text':row['text'],'row_id':row.get('id'),'start':aligned[0]['start'],'end':aligned[-1]['end'],
            'words':aligned,'confidence':confidence,'text_similarity':similarity,'path_score':float(scores[end]),'start_frame':start,'end_frame':int(end)})
    return sorted(proposals,key=lambda x:x['start'])


def text_key(row,vocab):
    from karaoke_ctc import normalized_words
    from karaoke_supplied_alignment import spoken
    try:return ''.join(normalized_words([{'word':t} for t in row['text'].split() if spoken(t)],vocab))
    except ValueError:return '\0unsupported:'+row['text']


def bound_terminal_phrase(hit,rows,views,vocab):
    """Verify a complete supplied prefix against its observed next word at EOF.

    The following word is context only: the unheard remainder is never copied.
    Two channels must corroborate every onset; uncertain endings retain review.
    """
    import torch
    import torchaudio.functional as AF
    from karaoke_ctc import normalized_words,words_from_spans
    from karaoke_supplied_alignment import spoken
    prefix=[w['word'] for w in hit['words']]
    normalized=normalized_words([{'word':t} for t in prefix],vocab)
    contexts=[]
    for row in rows:
        tokens=[t for t in row['text'].split() if spoken(t)]
        try:keys=normalized_words([{'word':t} for t in tokens],vocab)
        except ValueError:continue
        if len(keys)>len(normalized) and keys[:len(normalized)]==normalized:
            contexts.append(prefix+[tokens[len(prefix)]])
    if len(views)<2:return None
    for tokens in contexts:
        words=[{'word':t} for t in tokens]
        keys=normalized_words(words,vocab);targets=[vocab[c] for c in '|'.join(keys)]
        candidates=[]
        for view in views:
            a=max(0,round((hit['start']-.12)*50));b=len(view)
            try:
                path,scores=AF.forced_align(torch.from_numpy(view[a:b].copy())[None],
                    torch.tensor([targets],dtype=torch.int32),blank=vocab.get('[PAD]',0))
                spans=AF.merge_tokens(path[0],scores[0].exp(),blank=vocab.get('[PAD]',0))
                aligned=words_from_spans(words,keys,spans,targets,.02,a*.02)
            except (ValueError,RuntimeError):continue
            if min(w['probability'] for w in aligned)<.1:continue
            if sum(w['probability'] for w in aligned)/len(aligned)<.5:continue
            if aligned[-1]['probability']<.5:continue
            if abs(aligned[0]['start']-hit['start'])>.3:continue
            if aligned[-1]['start']-aligned[-2]['end']>3:continue
            candidates.append(aligned)
        if len(candidates)<2:continue
        if any(max(w['start'] for w in pair)-min(w['start'] for w in pair)>.3
               for pair in zip(*candidates)):continue
        result=[]
        next_start=min(c[-1]['start'] for c in candidates)
        for pair in zip(*(c[:-1] for c in candidates)):
            best=dict(max(pair,key=lambda w:w['probability']))
            best['end']=max(w['end'] for w in pair)
            if best['end']>next_start:return None
            best['needs_review']=best.get('needs_review',False) or max(w['end'] for w in pair)-min(w['end'] for w in pair)>.3
            result.append(best)
        return {**hit,'words':result,'start':result[0]['start'],'end':result[-1]['end'],
                'terminal_bounded':True}
    return None


def select_occurrences(rows,hits,vocab):
    """Joint non-overlap and supplied-order decoder; repeats cannot skip originals."""
    import bisect
    keys_by_text={r['text']:text_key(r,vocab) for r in [*rows,*hits]}
    keys=[keys_by_text[r['text']] for r in rows]
    # Equivalent punctuation/spacing variants compete for the same sound.
    unique={}
    for hit in hits:
        first=hit['words'][0]
        first_key=text_key({'text':first['word']},vocab)
        if len(hit['words'])>1 and len(first_key)<=2 and first['probability']<.35 and first['end']-first['start']<.12:
            # A weak short prefix alone cannot veto an otherwise well measured
            # verse (e.g. Kurdish "Li"). Reject a borrowed interjection only
            # when an independent suffix candidate explains the same sound.
            suffix=text_key({'text':' '.join(w['word'] for w in hit['words'][1:])},vocab)
            rivals=[other for other in hits if other is not hit and keys_by_text[other['text']]==suffix
                    and first['end']-.15<=other['start']<=hit['words'][1]['start']+.25
                    and abs(other['end']-hit['end'])<=.7 and other['confidence']>=.5]
            if rivals:continue
        key=keys_by_text[hit['text']];group=(key,round(hit['start']/.3),round(hit['end']/.3))
        if group not in unique or hit['confidence']>unique[group]['confidence']:unique[group]=hit
    candidates=list(unique.values())
    reliable=[]
    for hit in candidates:
        key=keys_by_text[hit['text']];reject=False
        for rival in candidates:
            if abs(hit['start']-rival['start'])>.35 or abs(hit['end']-rival['end'])>.7:continue
            other=keys_by_text[rival['text']]
            if key==other or key in other or other in key:continue
            if rival['path_score']-hit['path_score']>.6 and rival.get('text_similarity',0)-hit.get('text_similarity',0)>.08:
                reject=True;break
        if not reject:reliable.append(hit)
    hits=sorted(reliable,key=lambda h:h['end'])
    ends=[h['end'] for h in hits];n=len(rows);m=len(hits)
    scores=np.full((n+1,m+1),-1e9)
    back={};scores[0,0]=0
    for j in range(1,n+1):scores[j,0]=scores[j-1,0]-1000;back[(j,0)]=(j-1,0,None,'missing')
    for k,hit in enumerate(hits,1):
        previous=bisect.bisect_right(ends,hit['start']+.40,hi=k-1)
        key=keys_by_text[hit['text']]
        from karaoke_ctc import normalized_words
        normalized=normalized_words([{'word':w['word']} for w in hit['words']],vocab)
        weight=sum(len(text)*word['probability'] for text,word in zip(normalized,hit['words']))
        for j in range(n+1):
            scores[j,k]=scores[j,k-1];back[(j,k)]=(j,k-1,None,'carry')
            sources=[i for i in range(j) if keys[i]==key and not rows[i].get('locked')]
            if sources:
                candidate=scores[j,previous]+weight-.5
                if candidate>scores[j,k]:
                    scores[j,k]=candidate;back[(j,k)]=(j,previous,{**hit,'source_index':sources[-1]},'repeat')
            if j and keys[j-1]==key:
                candidate=scores[j-1,previous]+weight+1000
                if candidate>scores[j,k]:
                    scores[j,k]=candidate;back[(j,k)]=(j-1,previous,{**hit,'source_index':j-1},'original')
            if j and scores[j-1,k]-1000>scores[j,k]:
                scores[j,k]=scores[j-1,k]-1000;back[(j,k)]=(j-1,k,None,'missing')
    selected=[];j=n;k=m
    while j or k:
        previous_j,previous_k,hit,kind=back[(j,k)]
        if hit is not None:selected.append({**hit,'kind':kind,'slot':j})
        j,k=previous_j,previous_k
    return list(reversed(selected))


def waveform_repeat_hits(rows,hits,vocab,audio,rate):
    """Recover copies of verified phrases without lowering CTC thresholds.

    The existing repeat detector requires >.97 waveform correlation and >.95
    in three independent portions. A weak spelling prediction must not erase
    a phrase whose actual vocal waveform repeats elsewhere in the same song.
    """
    from karaoke_repeats import expand_repeats
    selected=select_occurrences(rows,hits,vocab)
    templates={f'occurrence:{i}':hit for i,hit in enumerate(selected)}
    references=[{'id':key,'text':hit['text'],'start':hit['start'],'end':hit['end'],'words':hit['words']}
                for key,hit in templates.items()]
    recovered,_=expand_repeats(references,None,audio_data=(audio,rate))
    additions=[]
    for row in recovered:
        source=templates.get(row.get('repeat_source_id'))
        if source is None:continue
        words=[{**w,'timing_reference':{'method':'waveform_repeat_match','reference_start':source['start'],
                'reference_end':source['end']}} for w in row['words']]
        additions.append({**source,'start':row['start'],'end':row['end'],'words':words,'acoustic_repeat':True})
    return additions


def expand_supplied_rows(rows,emission,vocab,progress=lambda *args:None,rescue=None,repeat_audio=None):
    import copy,hashlib
    views=emission if isinstance(emission,list) else [emission]
    seen=set();hits=[]
    for index,row in enumerate(rows):
        key=text_key(row,vocab)
        if key in seen:continue
        seen.add(key);progress(.9*index/max(1,len(rows)),f'Tekrar araması · satır {index+1}/{len(rows)} · {row["text"]}')
        for channel,view in enumerate(views):
            hits.extend({**hit,'channel':channel} for hit in find_occurrences(view,row,vocab,rescue=rescue,
                progress=lambda p,message:progress(.9*(index+(channel+p)/len(views))/max(1,len(rows)),
                    f'Satır {index+1}/{len(rows)} · '+message)))
    # Verify truncated terminal repetitions locally; do not invent an unobserved suffix.
    if rescue is not None:
        for row_index,row in enumerate(rows):
            progress(.9+.1*row_index/max(1,len(rows)),f'Eksik son kelime kontrolü · satır {row_index+1}/{len(rows)}')
            tokens=row['text'].split()
            if len(tokens)<3:continue
            prefix={**row,'text':' '.join(tokens[:-1])}
            for hit in find_occurrences(views[0],prefix,vocab):
                if any(text_key(h,vocab)==text_key(row,vocab) and h['start']<=hit['start']+.3 and h['end']>=hit['end']-.3 for h in hits):continue
                aligned=rescue(row,hit['start'],min(len(views[0])*.02,hit['end']+1.8))
                if not aligned:continue
                confidence=sum(w['probability'] for w in aligned)/len(aligned)
                if confidence<.4 or min(w['probability'] for w in aligned)<.1:continue
                hits.append({**hit,'text':row['text'],'row_id':row.get('id'),'start':aligned[0]['start'],
                             'end':aligned[-1]['end'],'words':aligned,'confidence':confidence,'recovery':'local_suffix'})
    acoustic_count=0
    if repeat_audio is not None:
        progress(.99,'Zayıf duyulan tekrarlar, aynı şarkının vokal dalgasıyla karşılaştırılıyor…')
        additions=waveform_repeat_hits(rows,hits,vocab,*repeat_audio)
        hits.extend(additions);acoustic_count=len(additions)
    progress(1.,'Bulunan tekrarların sırası ve çakışmaları kontrol ediliyor…')
    selected=select_occurrences(rows,hits,vocab)
    from karaoke_duplicate_repeats import archive_excess_repeats
    rows,archived_count=archive_excess_repeats(rows,selected,vocab)
    if archived_count:selected=select_occurrences(rows,hits,vocab)
    copies={};count=0;review=[];terminal_count=0
    for i,hit in enumerate(selected):
        key=text_key(hit,vocab)
        longer=[h for h in hits if text_key(h,vocab).startswith(key) and len(text_key(h,vocab))>len(key)/.8]
        if len(views[0])*.02-hit['end']>=2 or not longer:continue
        typical=float(np.median([h['end']-h['start'] for h in longer]))
        if len(views[0])*.02-hit['start']>=.8*typical:continue
        bounded=bound_terminal_phrase(hit,rows,views,vocab)
        if bounded:selected[i]=bounded
        else:hit['terminal_unverified']=True
    for hit in selected:
        if hit['kind']!='repeat':continue
        if len(rows)+count>=500:break
        source=rows[hit['source_index']]
        if not source.get('id'):continue
        if hit.get('terminal_unverified'):
            review.append({'text':source['text'],'start':hit['start'],'end':hit['end'],
                           'reason':'terminal_prefix_not_corroborated'})
            continue

        row=copy.deepcopy(source)
        row.pop('repeat_cleanup',None)
        row['_occurrence_words']=copy.deepcopy(hit['words'])
        if hit.get('acoustic_repeat'):row['_acoustic_occurrence']=True
        if hit.get('terminal_bounded'):
            row['_terminal_occurrence']=True;terminal_count+=1
        row.update(id='auto-repeat:'+hashlib.sha256((source['id']+str(round(hit['start'],2))).encode()).hexdigest()[:16],
                   repeat_source_id=source['id'],start=hit['start'],end=hit['end'],words=[],locked=False)
        copies.setdefault(hit['slot'],[]).append(row);count+=1
    result=[]
    for i,row in enumerate(rows):
        result.extend(copies.get(i,[]))
        original=copy.deepcopy(row)
        matching=next((h for h in selected if h['kind']=='original' and h['source_index']==i),None)
        if matching:
            original['_occurrence_words']=copy.deepcopy(matching['words'])
            if matching.get('acoustic_repeat'):original['_acoustic_occurrence']=True
            if matching.get('terminal_bounded'):original['_terminal_occurrence']=True
        result.append(original)
    result.extend(copies.get(len(rows),[]))
    return result,{'repeated_rows_added':count,'repeat_method':'supplied_text_ctc_occurrence_graph',
                   'repeat_accuracy_guaranteed':False,'repeat_candidates':len(hits),'repeat_review_candidates':review,
                   'terminal_repeats_added':terminal_count,'archived_duplicate_rows':archived_count,
                   'waveform_repeats_added':acoustic_count},selected


def local_verifier(audio,rate,model,extractor,vocab,device,progress=lambda *args:None,inference_cache=None):
    """Re-infer uncertain short passages, keeping the same acceptance thresholds."""
    from karaoke_inference import EmissionCache
    if inference_cache is None:inference_cache=EmissionCache(model,extractor,device)
    def verify(row,a,b):
        import torch
        import torchaudio.functional as AF
        from difflib import SequenceMatcher
        from karaoke_ctc import normalized_words,words_from_spans
        from karaoke_supplied_alignment import spoken,alignment_mono,rescue_weak_words
        words=[{'word':t} for t in row['text'].split() if spoken(t)]
        try:normalized=normalized_words(words,vocab)
        except ValueError:return None
        targets=[vocab[c] for c in '|'.join(normalized)]
        left=max(0,a-.1);right=min(len(audio)/rate,b+.1)
        if right-left>.02*max(500,len(targets)*40):return None
        clip=audio[round(left*rate):round(right*rate)]
        best=None;inverse={value:key for key,value in vocab.items()}
        progress(0,f'Tekrar kontrolü · {a:.2f}–{b:.2f} sn · {row["text"]}')
        for channel in ('mix','left','right'):
            mono=alignment_mono(clip) if channel=='mix' else clip[:,0 if channel=='left' else -1]
            emission=inference_cache.infer(mono,rate)
            if emission is None:continue
            ids=emission[0].argmax(-1).tolist()
            decoded=''.join(inverse[t] for i,t in enumerate(ids) if t not in (vocab.get('[PAD]',0),vocab['|']) and (i==0 or ids[i-1]!=t))
            if SequenceMatcher(None,''.join(normalized),decoded).ratio()<.5:continue
            try:
                path,scores=AF.forced_align(emission,torch.tensor([targets],dtype=torch.int32),blank=vocab.get('[PAD]',0))
                spans=AF.merge_tokens(path[0],scores[0].exp(),blank=vocab.get('[PAD]',0))
                aligned=words_from_spans(words,normalized,spans,targets,.02,left)
            except (ValueError,RuntimeError):continue
            rescue_weak_words(clip,rate,left,right,aligned,model,extractor,vocab,device,lambda p,message:progress(p,f'{a:.2f}–{b:.2f} sn · '+message),inference_cache=inference_cache)
            if min(w['probability'] for w in aligned)<.1:continue
            if sum(w['probability'] for w in aligned)/len(aligned)<.4:continue
            if any(w['end']<=w['start'] for w in aligned):continue
            if best is None or sum(w['probability'] for w in aligned)>sum(w['probability'] for w in best):best=aligned
        return best
    return verify
