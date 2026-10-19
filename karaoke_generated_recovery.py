"""Verify an audible prefix when an automatic repeat spills into music."""
import copy
from pathlib import Path


def recover_music_repeat_prefixes(vocal_path,original_path,rows,voice,music,language='kmr'):
    from karaoke_ctc import acoustic_probability,refine_ctc
    from karaoke_supplied_alignment import protected
    import soundfile as sf
    if not original_path or not Path(original_path).is_file():return 0
    if abs(sf.info(str(vocal_path)).duration-sf.info(str(original_path)).duration)>.05:return 0
    repaired=0
    for ri,row in enumerate(rows):
        if protected(row) or not str(row.get('id','')).startswith('auto-repeat:'):continue
        words=row.get('words') or []
        pending=[i for i,w in enumerate(words) if w.get('needs_review')]
        if not pending:continue
        first=pending[0]
        if first<2 or pending!=list(range(first,len(words))):continue
        left=words[first-1]['end'];right=words[first]['start']
        if right-left<3:continue
        ends=[b for a,b in voice if a<=left<=b and b<right-.2]
        if not ends:continue
        cutoff=max(ends)
        lower=max([0.,row['start']-.12]+[r['end'] for r in rows[:ri]])
        upper=min([cutoff+.12]+[r['start'] for r in rows[ri+1:]])
        if any(b>cutoff+.2 and a<words[-1]['end'] for a,b in voice):continue
        if not any(a<=left and b>=words[-1]['end'] for a,b in music):continue
        found=None
        for length in range(len(words),first-1,-1):
            context={**row,'text':' '.join(w['word'] for w in words[:length]),
                     'start':row['start'],'end':cutoff,'words':copy.deepcopy(words[:length])}
            views=[]
            for source,path in [('vocals',vocal_path),('original',original_path)]:
                try:
                    candidate=refine_ctc(str(path),[context],'kmr_mms' if language=='kmr' else 'tr_cv8',
                                         context_padding=.12,independent_rows=True)[0]['words']
                except (OSError,ValueError,RuntimeError):break
                if len(candidate)!=length or any(w.get('needs_review') or acoustic_probability(w)<.5 or
                        not lower<=w['start']<w['end']<=upper for w in candidate):break
                views.append(candidate)
            if len(views)!=2:continue
            if any(abs(a[k]-b[k])>.16 for a,b in zip(*views) for k in ('start','end')):continue
            found=[{**a,'start':(a['start']+b['start'])/2,'end':(a['end']+b['end'])/2,
                    'probability':min(acoustic_probability(a),acoustic_probability(b)),
                    'needs_review':False,'timing_source':'ctc',
                    'timing_reference':{'method':'dual_audio_generated_prefix',
                        'acoustically_verified':True,'bounds':[lower,upper],
                        'evidence':[copy.deepcopy(a),copy.deepcopy(b)]}}
                   for a,b in zip(*views)]
            break
        if not found:continue
        archived=copy.deepcopy(row);archived.pop('repeat_cleanup',None)
        row.setdefault('repeat_cleanup',[]).append({'row':archived,'matched_row_id':row['id'],
            'bounds':[row['start'],cutoff], 'reason':('unheard_generated_suffix_in_music'
                if len(found)<len(words) else 'generated_row_retimed_before_music')})
        row.update(words=found,text=' '.join(w['word'] for w in found),
                   start=found[0]['start'],end=found[-1]['end'])
        repaired+=1
    return repaired
