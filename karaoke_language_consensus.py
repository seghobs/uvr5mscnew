"""Supplement measured words with another language model without regressing them."""
import copy
import math


def merge_language_alignment(baseline, alternative, model_id):
    from karaoke_supplied_alignment import protected,instrumental
    result=copy.deepcopy(baseline)
    by_id={r.get('id'):r for r in alternative if r.get('id')}
    repaired=0
    for ri,row in enumerate(result):
        other=by_id.get(row.get('id'))
        if protected(row) or instrumental(row) or not other or other['text']!=row['text']:continue
        words=row.get('words') or [];proposals=other.get('words') or []
        if len(words)!=len(proposals):continue
        for j,(word,candidate) in enumerate(zip(words,proposals)):
            if word.get('timing_source')=='manual':continue
            if word['end']>word['start'] and not word.get('needs_review'):continue
            if word['word']!=candidate['word']:continue
            a,b=candidate['start'],candidate['end'];p=candidate.get('probability') or 0
            if not (all(math.isfinite(t) for t in (a,b,p)) and 0<=a<b and b-a<=6 and p>=.1):continue
            # A low-confidence alternative may supply a missing interval, but
            # must keep its warning. It cannot replace an already measured one.
            if word['end']>word['start'] and (p<.5 or candidate.get('needs_review')):continue
            lower=max([w['end'] for w in words[:j] if w['end']>w['start']]+
                      [r['end'] for r in result[:ri] if r['end']>r['start']],default=0)
            upper=min([w['start'] for w in words[j+1:] if w['end']>w['start']]+
                      [r['start'] for r in result[ri+1:] if r['end']>r['start']],default=math.inf)
            if not lower<=a<b<=upper:continue
            words[j]={**copy.deepcopy(candidate),'timing_reference':{
                'method':'language_model_alignment','model':model_id,
                'previous_source':word.get('timing_source')}}
            repaired+=1
        good=[w for w in words if w['end']>w['start']]
        if good:row['start']=good[0]['start'];row['end']=good[-1]['end']
    return result,repaired


def corroborate_recovered_repeats(audio_path,rows):
    """Audit recovered words against other occurrences; never invent a span.

    Short CTC tokens need a little acoustic context to avoid comparing a
    single FFT frame. Negative word examples must still discriminate the match.
    An absent or unconfirmed reference cannot clear a warning.
    """
    import numpy as np
    import soundfile as sf
    import librosa
    from karaoke_review_recovery import repeat_features
    audio,rate=sf.read(str(audio_path),dtype='float32',always_2d=True)
    entries=[(row.get('id'),w) for row in rows for w in row.get('words',[])]
    references=[(rid,w) for rid,w in entries if not w.get('needs_review') and
                (w.get('probability') or 0)>=.5 and w['end']>w['start']]
    cache={};count=0
    def key(w):return w['word'].strip('.,!?"').casefold()
    def features(w):
        span=(w['start'],w['end'])
        if span not in cache:
            a=max(0,int((span[0]-.06)*rate));b=min(len(audio),int((span[1]+.06)*rate))
            try:cache[span]=repeat_features(audio[a:b],rate)
            except (ValueError,FloatingPointError):cache[span]=None
        return cache[span]
    for rid,w in entries:
        provenance=w.get('timing_reference') or {}
        if provenance.get('method')!='language_model_alignment' or w['end']<=w['start']:continue
        candidates=[(refid,ref) for refid,ref in references if abs(ref['start']-w['start'])>1 and
                    .4<=(ref['end']-ref['start'])/max(.02,w['end']-w['start'])<=2.5]
        if sum(key(ref)==key(w) for _,ref in candidates)<2:continue
        target=features(w)
        if target is None:continue
        same=[];other=math.inf
        for refid,ref in candidates:
            feature=features(ref)
            if feature is None:continue
            try:distance,path=librosa.sequence.dtw(X=target,Y=feature,metric='cosine')
            except (ValueError,FloatingPointError):continue
            if not len(path):continue
            score=float(distance[-1,-1]/len(path))
            if not np.isfinite(score) or score<0:continue
            if key(ref)==key(w):same.append((score,refid))
            else:other=min(other,score)
        same.sort(key=lambda item:item[0])
        if len(same)>=2 and math.isfinite(other) and same[1][0]<.20 and same[1][0]<other*.75:
            provenance.update(repeat_row_ids=[r for _,r in same[:2]],
                              repeat_distances=[d for d,_ in same[:2]],negative_word_distance=other)
            w['timing_reference']=provenance;count+=1
    return count
