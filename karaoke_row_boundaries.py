"""Recheck a held line ending and the following word as one acoustic phrase."""
import copy
import math
import statistics

from karaoke_ctc import acoustic_probability
from karaoke_repeat_inference import measured, token_key


def suspicious_boundaries(rows):
    """A long first word is a retry trigger, never proof of a wrong onset."""
    from karaoke_supplied_alignment import instrumental, protected
    targets=[]
    for index in range(1,len(rows)):
        left,right=rows[index-1:index+1]
        if any(instrumental(r) or protected(r) for r in (left,right)):continue
        before,after=left.get('words') or [],right.get('words') or []
        if len(before)<2 or len(after)<2:continue
        tail,head=before[-1],after[0]
        if any(w.get('timing_source')=='manual' for w in (tail,head)):continue
        if not tail.get('needs_review') and acoustic_probability(tail)>=.5:continue
        if not (0<=tail['start']<tail['end']<=head['start']<head['end']):continue
        if head['start']-tail['end']>1.5 or right['end']-left['start']>18:continue
        donors=[r['words'][0]['end']-r['words'][0]['start'] for ri,r in enumerate(rows)
                if ri!=index and r.get('words') and measured(r['words'][0])
                and token_key(r['words'][0]['word'])==token_key(head['word'])]
        if donors and head['end']-head['start']>max(1.5,2*statistics.median(donors)+.25):
            targets.append(index)
    return targets


def apply_boundary_candidates(rows,index,candidates,duration):
    """Apply only two agreeing joint acoustic retries, preserving inner words."""
    from karaoke_supplied_alignment import protected
    left,right=rows[index-1:index+1]
    if protected(left) or protected(right):return False
    tail,head=left['words'][-1],right['words'][0]
    if any(w.get('timing_source')=='manual' for w in (tail,head)):return False
    lower=left['words'][-2]['end'];upper=right['words'][1]['start']
    usable=[]
    for candidate in candidates:
        pair=candidate['rows']
        if len(pair)!=2 or any(a['text']!=b['text'] or
                [w['word'] for w in a.get('words') or []]!=[w['word'] for w in b['words']]
                for a,b in zip((left,right),pair)):continue
        a,b=pair[0]['words'][-1],pair[1]['words'][0]
        if any(acoustic_probability(w)<.5 or w.get('needs_review') for w in (a,b)):continue
        if not all(math.isfinite(w[k]) for w in (a,b) for k in ('start','end')):continue
        if not (0<=lower<=a['start']<a['end']<=b['start']<b['end']<=min(upper,duration)):continue
        # Keep the stable sides of the two words anchored. Only the disputed
        # row transition may move substantially; never trim text to make it fit.
        if (abs(a['start']-tail['start'])>.18 or abs(b['end']-head['end'])>.20
                or b['start']<head['start']+.35 or a['end']<tail['end']-.15
                or b['end']-b['start']>(head['end']-head['start'])*.65):continue
        usable.append((candidate,a,b))
    pairs=[]
    for i,a in enumerate(usable):
        for b in usable[i+1:]:
            if (a[0]['model'],a[0]['channel'])==(b[0]['model'],b[0]['channel']):continue
            if all(abs(a[j][k]-b[j][k])<=.16 for j in (1,2) for k in ('start','end')):
                pairs.append((a,b))
    if not pairs:return False
    first,second=max(pairs,key=lambda p:min(acoustic_probability(w) for x in p for w in x[1:]))
    for part,(row,wi,old) in enumerate(((left,len(left['words'])-1,tail),(right,0,head)),1):
        a,b=first[part],second[part]
        row['words'][wi]={**old,'start':(a['start']+b['start'])/2,'end':(a['end']+b['end'])/2,
            'probability':min(acoustic_probability(a),acoustic_probability(b)),
            'timing_source':'ctc','needs_review':False,'timing_reference':{
                'method':'joint_row_boundary_consensus','acoustically_verified':True,
                'previous_start':old['start'],'previous_end':old['end'],
                'row_ids':[left.get('id'),right.get('id')],
                'evidence':[{'model':x[0]['model'],'channel':x[0]['channel'],
                             'tail':copy.deepcopy(x[1]),'head':copy.deepcopy(x[2])} for x in (first,second)]}}
    left['end']=left['words'][-1]['end'];right['start']=right['words'][0]['start']
    return True


def recover_row_boundaries(audio_path,rows,progress=lambda *args:None,language='tr'):
    targets=suspicious_boundaries(rows)
    report={'row_boundary_repairs':0,'row_boundary_review_rows':[]}
    if not targets:return report
    import soundfile as sf
    from karaoke_ctc import refine_ctc
    from karaoke_inference import RefinementSession
    models={'tr':('tr','tr_mms'),'kmr':('kmr_mms','kmr'),
            'en':('en','en_lv60'),'az':('az',)}[language]
    frozen=copy.deepcopy(rows);duration=sf.info(str(audio_path)).duration
    candidates={index:[] for index in targets};pending=set(targets)
    with RefinementSession() as session:
        for model in models:
            for channel in ('left','right'):
                for index in sorted(pending):
                    label=f'Satır geçişi kontrol ediliyor · {index}–{index+1} · {model} · {channel}'
                    progress(.99,label)
                    try:
                        pair=refine_ctc(str(audio_path),copy.deepcopy(frozen[index-1:index+1]),model,
                            context_padding=.8,channel=channel,session=session)
                    except Exception as exc:
                        report.setdefault('row_boundary_errors',[]).append({'model':model,'error':str(exc)})
                        continue
                    candidates[index].append({'model':model,'channel':channel,'rows':pair})
                    if apply_boundary_candidates(rows,index,candidates[index],duration):
                        pending.remove(index);report['row_boundary_repairs']+=1
    report['row_boundary_review_rows']=[index+1 for index in sorted(pending)]
    for index in pending:
        # A suspected early handoff must remain visible if retries disagree.
        rows[index]['words'][0]['needs_review']=True
    return report
