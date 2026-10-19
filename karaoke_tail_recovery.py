"""Recover quiet endings, then label repeat-based estimates as estimates."""
import copy
import math
import statistics


def confirmed(word):
    return (not word.get('needs_review') and word.get('timing_source') in ('ctc','aligned','manual')
            and all(isinstance(word.get(k),(int,float)) and math.isfinite(word[k]) for k in ('start','end'))
            and 0<=word['start']<word['end'])


def infer_tail_from_repeats(rows,duration,duration_only=False):
    """Use only matching earlier verses with consistent measured anchor words.

    No equal-duration splitting, no invented acoustic confidence, and no changes
    to manual/locked words. The caller first establishes that the audio fades.
    """
    from karaoke_supplied_alignment import instrumental,protected
    if duration_only:
        return infer_tail_durations(rows,duration)
    import unicodedata
    def key(text):
        return ''.join(c for c in text.replace('I','ı').replace('İ','i').lower()
                       if not unicodedata.category(c).startswith('P')).split()
    indices=[i for i,r in enumerate(rows) if not instrumental(r) and r.get('words')]
    if not indices:return 0
    index=indices[-1];row=rows[index];words=row['words']
    if protected(row) or duration-row['start']>20:return 0
    pending=[i for i,w in enumerate(words) if not confirmed(w)]
    if not pending:return 0
    first=pending[0]
    # Only an uncertain trailing run, never a gap among confirmed later words.
    if pending!=list(range(first,len(words))) or first<3:return 0
    anchors=list(range(first));proposals=[];references=[]
    for ri,reference in enumerate(rows[:index]):
        rw=reference.get('words') or []
        if key(reference['text'])!=key(row['text']) or len(rw)!=len(words) or not all(confirmed(w) for w in rw):continue
        pairs=[(rw[j][edge],words[j][edge]) for j in anchors for edge in ('start','end')]
        slopes=[(y2-y1)/(x2-x1) for p,(x1,y1) in enumerate(pairs) for x2,y2 in pairs[p+1:] if x2-x1>=1.]
        if not slopes:continue
        scale=statistics.median(slopes)
        if not .85<=scale<=1.15:continue
        offset=statistics.median(y-scale*x for x,y in pairs)
        if max(abs(y-(scale*x+offset)) for x,y in pairs)>.18:continue
        proposals.append([(scale*w['start']+offset,scale*w['end']+offset) for w in rw[first:]])
        references.append(reference.get('id') or f'row:{ri+1}')
    if not proposals:return 0
    inferred=[];previous=words[first-1]['end']
    for j in range(len(pending)):
        starts=[p[j][0] for p in proposals];ends=[p[j][1] for p in proposals]
        if max(starts)-min(starts)>.45 or max(ends)-min(ends)>.55:return 0
        start=statistics.median(starts);end=min(duration,statistics.median(ends))
        if start<previous or end-start<.08 or end-start>3:return 0
        inferred.append((start,end));previous=end
    for j,(start,end) in zip(pending,inferred):
        words[j]={**words[j],'start':start,'end':end,'timing_source':'repeat_inferred',
                  'probability':None,'needs_review':False,
                  'timing_reference':{'row_ids':references,'anchor_words':len(anchors),'method':'matching_verse_tempo'}}
    row['end']=max(row['end'],words[-1]['end'])
    return len(inferred)


def infer_tail_durations(rows,duration):
    """Use donor lengths only; placement comes from this tail's weak CTC path."""
    from karaoke_supplied_alignment import instrumental,protected
    from karaoke_repeat_inference import measured,token_key
    candidates=[i for i,r in enumerate(rows) if not instrumental(r) and r.get('words')]
    if not candidates:return 0
    ri=candidates[-1];row=rows[ri];words=row['words']
    pending=[i for i,w in enumerate(words) if not confirmed(w)]
    if protected(row) or not pending or not 0<duration-row['start']<=20:return 0
    first=pending[0]
    if first<3 or pending!=list(range(first,len(words))):return 0
    snapshot=copy.deepcopy(words);planned=[];lower=words[first-1]['end']
    if any(w.get('timing_source')=='manual' for w in snapshot[first:]):return 0
    upper=min([duration]+[r['start'] for r in rows[ri+1:]])
    for wi in pending:
        w=snapshot[wi];refs=[(r.get('id') or f'row:{j+1}',v) for j,r in enumerate(rows[:ri])
            for v in r.get('words',[]) if measured(v) and token_key(v['word'])==token_key(w['word'])]
        if not refs:return 0
        length=statistics.median(v['end']-v['start'] for _,v in refs)
        ref=w.get('timing_reference') or {}
        a,b=(w['start'],w['end']) if w['end']>w['start'] else (ref.get('previous_start'),ref.get('previous_end'))
        if not all(isinstance(t,(int,float)) and math.isfinite(t) for t in (a,b)) or not row['start']<=a<b<=upper:return 0
        # Never import donor offsets or donor inter-word gaps.
        start=max(lower,(a+b-length)/2);end=start+length
        if not .019<=length<=3 or end>upper:return 0
        planned.append((wi,{**w,'start':start,'end':end,'probability':None,'needs_review':False,
            'timing_source':'repeat_inferred','timing_reference':{
                'method':'same_word_tail_duration_only','row_ids':list(dict.fromkeys(k for k,_ in refs)),
                'anchor_words':first,'duration_only':True,'reference_duration_seconds':length,
                'acoustically_verified':False,'bounds':[lower,upper],
                'previous_start':a,'previous_end':b}}))
        lower=end
    for wi,w in planned:words[wi]=w
    row['end']=max(w['end'] for w in words)
    return len(planned)


def recover_fading_tail(audio_path,rows,progress=lambda *args:None,language='tr'):
    import numpy as np
    import soundfile as sf
    from karaoke_ctc import refine_turkish,refine_ctc
    refine=refine_turkish if language=='tr' else refine_ctc
    from karaoke_supplied_alignment import instrumental,protected,choose_boundary_candidate
    indices=[i for i,r in enumerate(rows) if not instrumental(r) and r.get('words')]
    report={'quiet_tail_repaired_words':0,'repeat_inferred_words':0}
    if not indices:return report
    row=rows[indices[-1]];pending=[j for j,w in enumerate(row['words']) if not confirmed(w)]
    if protected(row) or not pending:return report
    info=sf.info(str(audio_path));duration=info.duration
    if not 0<duration-row['start']<=20:return report
    audio,rate=sf.read(str(audio_path),start=max(0,int(row['start']*info.samplerate)),dtype='float32',always_2d=True)
    energy=np.mean(audio*audio,axis=1);hop=max(1,int(rate*.25))
    levels=np.array([np.sqrt(np.mean(energy[i:i+hop])) for i in range(0,len(energy),hop)])
    # Restrict extrapolation to an actual diminishing/cut-off ending.
    if len(levels)<8 or levels.max()<1e-5 or np.median(levels[-4:])>levels.max()*.2:return report
    progress(.99,'Kısık kapanış kontrol ediliyor; gerekirse önceki tekrardan tahmini süre hazırlanıyor…')
    context=copy.deepcopy(row);context['end']=duration
    candidates={j:[] for j in pending}
    for channel in ('mix','left','right'):
        refined=refine(str(audio_path),[context],language,context_padding=.5,channel=channel,normalize_fade=True)[0]
        for j in pending:candidates[j].append({**refined['words'][j],'recovery_channel':channel})
    for j in pending:
        lower=max((w['end'] for w in row['words'][:j] if confirmed(w)),default=row['start'])
        upper=min((w['start'] for w in row['words'][j+1:] if confirmed(w)),default=duration)
        original=row['words'][j]
        selected=choose_boundary_candidate(original,candidates[j],lower,upper)
        # A recovered word must not overlap another retained interval. Weak
        # trailing intervals are replaced together by the repeat inference.
        if selected is not original:
            row['words'][j]=selected;report['quiet_tail_repaired_words']+=1
    report['repeat_inferred_words']=infer_tail_from_repeats(rows,duration,duration_only=True)
    # If extrapolation was rejected, retain the original unresolved words and
    # do not introduce overlaps while repairing their neighbours.
    for j in pending:
        word=row['words'][j]
        if j+1<len(row['words']):
            nxt=row['words'][j+1]
            if nxt['end']>nxt['start'] and word['end']>nxt['start']:
                row['words'][j]=copy.deepcopy(context['words'][j])
                if confirmed(word):report['quiet_tail_repaired_words']-=1
    valid=[w for w in row['words'] if w['end']>w['start']]
    if valid:row['end']=max(row['end'],max(w['end'] for w in valid))
    return report
