"""Audit every located phrase, including confident mistakes, before local repair.

Model agreement is corroboration, never a guarantee or human ground truth.
Existing strong timings are flagged on disagreement, not silently replaced.
"""
import copy
import itertools
import math

from karaoke_ctc import acoustic_probability,has_timed_row
from karaoke_repeat_inference import token_key


def consensus(proposals,tolerance=.12):
    usable=[p for p in proposals if acoustic_probability(p)>=.55 and
            all(isinstance(p.get(k),(float,int)) and math.isfinite(p[k]) for k in ('start','end')) and
            0<=p['start']<p['end'] and not p.get('needs_review')]
    # At most one vote per model/audio view; repeated contexts cannot vote twice.
    unique={}
    for p in usable:
        identity=(p['model'],p['source'])
        if identity not in unique or acoustic_probability(p)>acoustic_probability(unique[identity]):unique[identity]=p
    usable=list(unique.values());groups=[]
    for size in range(2,len(usable)+1):
        for group in itertools.combinations(usable,size):
            if len({p['model'] for p in group})<2:continue
            if any(max(p[k] for p in group)-min(p[k] for p in group)>tolerance for k in ('start','end')):continue
            rank=(len(group),len({p['source'] for p in group}),min(acoustic_probability(p) for p in group))
            groups.append((rank,group))
    if not groups:return None
    groups.sort(key=lambda x:x[0],reverse=True);rank,best=groups[0]
    start=sum(p['start'] for p in best)/len(best);end=sum(p['end'] for p in best)/len(best)
    # Equally supported but disjoint occurrences must not be decided by score.
    for other_rank,other in groups[1:]:
        if other_rank[:2]!=rank[:2]:continue
        if abs(sum(p['start'] for p in other)/len(other)-start)>.16:return None
    return {'start':start,'end':end,'probability':rank[2],'evidence':copy.deepcopy(list(best))}


def apply_phrase_audit(rows,candidates,duration):
    from karaoke_supplied_alignment import instrumental
    report={'phrase_audited_words':0,'phrase_audited_keys':[],'phrase_disagreements':0,'phrase_repaired_words':0,'phrase_unverified_words':0}
    frozen=copy.deepcopy(rows)
    for ri,row in enumerate(rows):
        if row.get('locked') or instrumental(row):continue
        for wi,word in enumerate(row.get('words') or []):
            if word.get('timing_source')=='manual':continue
            proposals=[p for p in candidates.get((row.get('id') or f'row:{ri+1}',wi),[]) if token_key(p['word'])==token_key(word['word'])]
            vote=consensus(proposals)
            if vote is None:
                report['phrase_unverified_words']+=1;continue
            report['phrase_audited_words']+=1
            report['phrase_audited_keys'].append([row.get('id') or f'row:{ri+1}',wi])
            matches=word['end']>word['start'] and all(abs(word[k]-vote[k])<=.16 for k in ('start','end'))
            word['alignment_audit']={'method':'phrase_multimodel_consensus','status':'agrees' if matches else 'disagrees',
                                     'proposal':[vote['start'],vote['end']], 'evidence':vote['evidence']}
            if not word.get('needs_review') and acoustic_probability(word)>=.5:
                if not matches:word['needs_review']=True;report['phrase_disagreements']+=1
                continue
            # Constrain the proposal to existing neighbours. A phrase cannot
            # silently borrow the preceding sustained ending or the next word.
            lower=max([0.]+[r['end'] for r in frozen[:ri] if has_timed_row(r)]+
                      [w['end'] for w in frozen[ri].get('words',[])[:wi] if w['end']>w['start']])
            upper=min([duration]+[r['start'] for r in frozen[ri+1:] if has_timed_row(r)]+
                      [w['start'] for w in frozen[ri].get('words',[])[wi+1:] if w['end']>w['start']])
            if not lower<=vote['start']<vote['end']<=upper:
                word['needs_review']=True;continue
            word.update(start=vote['start'],end=vote['end'],probability=vote['probability'],timing_source='ctc',needs_review=False)
            word['timing_reference']={'method':'phrase_multimodel_consensus','acoustically_verified':True,'evidence':vote['evidence']}
            word.pop('syllables',None)
            report['phrase_repaired_words']+=1
        valid=[w for w in row.get('words') or [] if w['end']>w['start']]
        if valid:row['start']=min(row['start'],valid[0]['start']);row['end']=max(row['end'],valid[-1]['end'])
    return report


def collect_phrase_evidence(vocal_path,original_path,rows,progress,language='tr'):
    from pathlib import Path
    import soundfile as sf
    from karaoke_ctc import refine_ctc
    from karaoke_inference import RefinementSession
    from karaoke_supplied_alignment import instrumental,protected
    from karaoke_alignment_models import model_spec
    info=sf.info(str(vocal_path));duration=info.duration
    selected=[];report={'phrase_skipped_rows':[],'phrase_audit_errors':[]}
    for ri,row in enumerate(rows):
        if instrumental(row) or protected(row):continue
        if not has_timed_row(row) or row['end']-row['start']>18:
            report['phrase_skipped_rows'].append(ri+1);continue
        item=copy.deepcopy(row);item['_audit_key']=row.get('id') or f'row:{ri+1}'
        item['words']=[{k:v for k,v in w.items() if k in ('word','start','end','probability','timing_source','needs_review')} for w in item.get('words') or []]
        selected.append(item)
    sources=[('vocals',vocal_path)]
    if original_path and Path(original_path).is_file() and abs(sf.info(str(original_path)).duration-duration)<=.05:sources.append(('original',original_path))
    models={'tr':('tr','tr_mms'),'kmr':('kmr','kmr_mms'),'en':('en','en_lv60'),'az':('az',)}[language]
    evidence={}
    if not selected:return evidence,report
    with RefinementSession() as session:
        for model in models:
            directory,model_id,_=model_spec(model)
            if not any((directory/file).is_file() for file in ('model.safetensors','pytorch_model.bin')):
                report['phrase_audit_errors'].append({'model':model_id,'reason':'model_not_installed'});continue
            for source,path in sources:
                label=f'Tüm satırlar çapraz denetleniyor · {model} · {source}'
                progress(.99,label)
                try:
                    proposed=refine_ctc(str(path),selected,model,context_padding=.45,independent_rows=True,
                        include_syllables=language=='tr',session=session,progress=lambda p,m:progress(.99,label+' · '+m))
                    for row in proposed:
                        for wi,word in enumerate(row.get('words') or []):
                            evidence.setdefault((row['_audit_key'],wi),[]).append({**word,'model':model_id,'source':source})
                except Exception as exc:report['phrase_audit_errors'].append({'model':model_id,'source':source,'reason':str(exc)})
    return evidence,report


def attach_consensus_syllables(rows,evidence,language='tr'):
    """Persist measured Turkish syllables only; never divide duration evenly."""
    report={'automatic_syllables':0,'syllable_words':0,'syllable_language':language,'syllable_supported':language=='tr'}
    if language!='tr':return report
    for ri,row in enumerate(rows):
        if row.get('locked'):continue
        for wi,word in enumerate(row.get('words') or []):
            if word.get('timing_source') in ('manual','estimated','repeat_inferred') or word.get('needs_review'):continue
            proposals=evidence.get((row.get('id') or f'row:{ri+1}',wi),[])
            tail=word.get('timing_reference') or {}
            held_end=tail.get('method')=='vocal_sustain_endpoint' and tail.get('scope')=='end_only'
            usable=[p for p in proposals if p.get('syllables') and token_key(p['word'])==token_key(word['word']) and
                    abs(p['start']-word['start'])<=.16 and (abs(p['end']-word['end'])<=.16 or
                    (held_end and abs(p['end']-tail.get('previous_end',word['end']))<=.16 and p['end']<=word['end']))]
            counts={len(p['syllables']) for p in usable};accepted=None
            for count in sorted(counts,reverse=True):
                group=[p for p in usable if len(p['syllables'])==count]
                parts=[];previous=word['start']
                for si in range(count):
                    options=[{**s,'probability':s.get('score',0),'needs_review':False,'model':p['model'],'source':p['source']}
                             for p in group for s in [p['syllables'][si]] if token_key(s['text'])==token_key(group[0]['syllables'][si]['text'])]
                    vote=consensus(options,.08)
                    if vote is None or not word['start']<=previous<=vote['start']<vote['end']<=word['end']:break
                    parts.append({'text':group[0]['syllables'][si]['text'],'start':vote['start'],'end':vote['end'],
                                  'score':vote['probability'],'needs_review':False,'timing_source':'ctc'})
                    previous=vote['end']
                if len(parts)==count and token_key(''.join(p['text'] for p in parts))==token_key(word['word']):accepted=parts;break
            if accepted:
                if held_end and word['end']>accepted[-1]['end']:accepted[-1]['end']=word['end']
                word['syllable_reference']={'word_start':word['start'],'word_end':word['end'],'word_text':word['word']}
                word['syllables']=accepted;report['automatic_syllables']+=len(accepted);report['syllable_words']+=1
    return report
