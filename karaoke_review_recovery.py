"""Confirm weak CTC boundaries against a verified repetition in the same audio."""
import math
import copy


def recover_row_reviews(audio_path,rows,progress=lambda *args:None):
    """A full-line acoustic retry complements the bounded local phrase retry."""
    from karaoke_ctc import refine_turkish
    from karaoke_supplied_alignment import choose_boundary_candidate,protected,instrumental
    pending=[i for i,row in enumerate(rows) if not protected(row) and any(w.get('needs_review') for w in row.get('words') or [])]
    if not pending:return 0
    context=sorted({j for i in pending for j in range(max(0,i-1),min(len(rows),i+2)) if not instrumental(rows[j]) and rows[j].get('words')})
    candidates={};count=0
    for padding,channel in ((p,c) for p in (.25,1.4) for c in ('mix','left','right')):
        progress(.99,'Kalan belirsiz kelimeler tam satır bağlamıyla kontrol ediliyor…')
        refined=refine_turkish(audio_path,[copy.deepcopy(rows[i]) for i in context],'tr',context_padding=padding,channel=channel)
        for index,row in zip(context,refined):
            for j,word in enumerate(row.get('words') or []):candidates.setdefault((index,j),[]).append({**word,'recovery_channel':channel})
    for index in pending:
        row=rows[index]
        for j,word in enumerate(row.get('words') or []):
            if not word.get('needs_review'):continue
            lower=row['words'][j-1]['end'] if j else rows[index-1]['end'] if index else 0
            upper=row['words'][j+1]['start'] if j+1<len(row['words']) else rows[index+1]['start'] if index+1<len(rows) else math.inf
            selected=choose_boundary_candidate(word,candidates[(index,j)],lower,upper)
            if selected is not word:row['words'][j]=selected;count+=1
        good=[w for w in row['words'] if w['end']>w['start']]
        if good:row['start']=min(row['start'],good[0]['start']);row['end']=max(row['end'],good[-1]['end'])
    return count


def repeat_boundary_candidate(original,candidates,lower,upper,same_distance,other_distance):
    if not (math.isfinite(same_distance) and same_distance<.20 and same_distance<other_distance*.75):return original
    usable=[c for c in candidates if c.get('probability',0)>=.30 and lower<=c['start']<c['end']<=upper
            and abs(c['start']-original['start'])<=.25 and abs(c['end']-original['end'])<=.25]
    pairs=[(a,b) for i,a in enumerate(usable) for b in usable[i+1:]
           if a.get('recovery_channel')!=b.get('recovery_channel')
           and abs(a['start']-b['start'])<=.04 and abs(a['end']-b['end'])<=.04]
    if not pairs:return original
    a,b=max(pairs,key=lambda pair:min(pair[0]['probability'],pair[1]['probability']))
    return {**original,'start':(a['start']+b['start'])/2,'end':(a['end']+b['end'])/2,
            'probability':min(a['probability'],b['probability']),'timing_source':'ctc','needs_review':False}


def repeated_audio_support(audio,rate,offset,words,index,cache):
    import numpy as np
    import librosa
    from karaoke_supplied_alignment import alignment_mono
    target=words[index]
    references=[(i,w) for i,w in enumerate(words) if i!=index and not w.get('needs_review')
                and (w.get('probability') or 0)>=.5 and w['end']-w['start']>=.08]
    def key(w):return w['word'].strip('.,!?"').casefold()
    if not any(key(w)==key(target) for _,w in references):return math.inf,math.inf
    def features(w):
        span=(w['start'],w['end'])
        if span not in cache:
            clip=audio[max(0,round((w['start']-offset)*rate)):round((w['end']-offset)*rate)]
            clip=alignment_mono(clip)
            wave=librosa.resample(clip,orig_sr=rate,target_sr=16000)
            if len(wave)<400:return None
            mfcc=librosa.feature.mfcc(y=wave,sr=16000,n_mfcc=16,n_fft=400,hop_length=160)[2:]
            cache[span]=mfcc/(np.linalg.norm(mfcc,axis=0,keepdims=True)+1e-6)
        return cache[span]
    source=features(target)
    if source is None:return math.inf,math.inf
    same=other=math.inf
    for _,word in references:
        reference=features(word)
        if reference is None:continue
        try:distances,path=librosa.sequence.dtw(X=source,Y=reference,metric='cosine')
        except ValueError:continue
        score=float(distances[-1,-1]/len(path))
        if key(word)==key(target):same=min(same,score)
        else:other=min(other,score)
    return same,other
