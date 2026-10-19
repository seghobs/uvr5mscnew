"""Confirm weak CTC boundaries against a verified repetition in the same audio."""
import math
import copy
from karaoke_ctc import acoustic_probability


def recover_row_reviews(audio_path,rows,progress=lambda *args:None,language='tr'):
    """A full-line acoustic retry complements the bounded local phrase retry."""
    from karaoke_ctc import refine_turkish,refine_ctc
    refine=refine_turkish if language=='tr' else refine_ctc
    from karaoke_supplied_alignment import choose_boundary_candidate,protected,instrumental
    pending=[i for i,row in enumerate(rows) if not protected(row) and any(w.get('needs_review') for w in row.get('words') or [])]
    if not pending:return 0
    context=sorted({j for i in pending for j in range(max(0,i-1),min(len(rows),i+2)) if not instrumental(rows[j]) and rows[j].get('words')})
    candidates={};count=0
    passes=([(p,c,False) for p in (.25,1.4) for c in ('mix','left','right')] if language=='tr' else
            [(p,c,independent) for independent in (False,True) for p in (.25,.8,1.4) for c in ('left','right')])
    for padding,channel,independent in passes:
        progress(.99,'Kalan belirsiz kelimeler tam satır bağlamıyla kontrol ediliyor…')
        options={} if language=='tr' else {'independent_rows':independent}
        refined=refine(audio_path,[copy.deepcopy(rows[i]) for i in context],language,context_padding=padding,channel=channel,**options)
        for index,row in zip(context,refined):
            for j,word in enumerate(row.get('words') or []):candidates.setdefault((index,j),[]).append({**word,'recovery_channel':channel})
    for index in pending:
        row=rows[index]
        for j,word in enumerate(row.get('words') or []):
            if not word.get('needs_review'):continue
            lower=row['words'][j-1]['end'] if j else rows[index-1]['end'] if index else 0
            upper=row['words'][j+1]['start'] if j+1<len(row['words']) else rows[index+1]['start'] if index+1<len(rows) else math.inf
            selected=choose_boundary_candidate(word,candidates[(index,j)],lower,upper)
            if selected is not word:
                if language=='kmr_mms':
                    selected['timing_reference']={'method':'language_model_channel_consensus',
                                                 'model':'facebook/mms-1b-all','adapter':'kmr-script_latin'}
                row['words'][j]=selected;count+=1
        good=[w for w in row['words'] if w['end']>w['start']]
        if good:row['start']=min(row['start'],good[0]['start']);row['end']=max(row['end'],good[-1]['end'])
    return count


def repeat_boundary_candidate(original,candidates,lower,upper,same_distance,other_distance):
    if not (math.isfinite(same_distance) and math.isfinite(other_distance) and
            0<=same_distance<.20 and same_distance<other_distance*.75):return original
    usable=[c for c in candidates if acoustic_probability(c)>=.30 and lower<=c['start']<c['end']<=upper
            and abs(c['start']-original['start'])<=.25 and abs(c['end']-original['end'])<=.25]
    pairs=[(a,b) for i,a in enumerate(usable) for b in usable[i+1:]
           if a.get('recovery_channel')!=b.get('recovery_channel')
           and abs(a['start']-b['start'])<=.04 and abs(a['end']-b['end'])<=.04]
    if not pairs:return original
    a,b=max(pairs,key=lambda pair:min(pair[0]['probability'],pair[1]['probability']))
    return {**original,'start':(a['start']+b['start'])/2,'end':(a['end']+b['end'])/2,
            'probability':min(a['probability'],b['probability']),'timing_source':'ctc','needs_review':False}


def repeat_features(clip,rate):
    """Reject silent/invalid references without compressing gaps into speech."""
    import numpy as np
    import librosa
    from karaoke_supplied_alignment import alignment_mono
    if not len(clip) or not np.isfinite(clip).all():return None
    wave=librosa.resample(alignment_mono(clip),orig_sr=rate,target_sr=16000)
    if len(wave)<400 or not np.isfinite(wave).all():return None
    # A word stretched over an instrumental break is not a trustworthy
    # repetition reference, even when its CTC average score looks plausible.
    rms=librosa.feature.rms(y=wave,frame_length=400,hop_length=160)[0]
    if not len(rms) or rms.max()<1e-5:return None
    quiet=rms<max(1e-5,float(rms.max())*.01)
    run=0
    for frame in quiet:
        run=run+1 if frame else 0
        if run>=12:return None  # 120 ms of near-silence; do not splice it out.
    mfcc=librosa.feature.mfcc(y=wave,sr=16000,n_mfcc=16,n_fft=400,hop_length=160)[2:]
    norm=np.linalg.norm(mfcc,axis=0,keepdims=True)
    # Adding epsilon to a zero vector still leaves it zero. Cosine distance
    # would divide by zero again inside DTW, so such evidence must be rejected.
    if not np.isfinite(mfcc).all() or not np.isfinite(norm).all() or np.any(norm<=1e-8):return None
    return mfcc/norm


def repeated_audio_support(audio,rate,offset,words,index,cache):
    import librosa
    from librosa.util.exceptions import ParameterError
    target=words[index]
    references=[(i,w) for i,w in enumerate(words) if i!=index and not w.get('needs_review')
                and (w.get('probability') or 0)>=.5 and w['end']-w['start']>=.08]
    def key(w):return w['word'].strip('.,!?"').casefold()
    if not any(key(w)==key(target) for _,w in references):return math.inf,math.inf
    def features(w):
        span=(w['start'],w['end'])
        if span not in cache:
            cache[span]=None
            if not all(math.isfinite(t) for t in span) or span[1]<=span[0]:return None
            first=max(0,round((w['start']-offset)*rate));last=min(len(audio),round((w['end']-offset)*rate))
            if last<=first:return None
            try:cache[span]=repeat_features(audio[first:last],rate)
            except (ParameterError,ValueError,FloatingPointError):pass
        return cache[span]
    source=features(target)
    if source is None:return math.inf,math.inf
    same=other=math.inf
    for _,word in references:
        reference=features(word)
        if reference is None:continue
        try:distances,path=librosa.sequence.dtw(X=source,Y=reference,metric='cosine')
        except (ParameterError,ValueError,FloatingPointError):continue
        if not len(path):continue
        score=float(distances[-1,-1]/len(path))
        if not math.isfinite(score) or score<0:continue
        if key(word)==key(target):same=min(same,score)
        else:other=min(other,score)
    return same,other
