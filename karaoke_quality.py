"""Fail-safe refinement stages and an honest, model-independent quality report."""
import copy
import math

from karaoke_timing import is_music_label, render_timing_issues


def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def structural_faults(rows,duration):
    faults=set();previous=0.;seen=set()
    for ri,row in enumerate(rows):
        key=row.get('id') or f'row:{ri}'
        if row.get('id') in seen:faults.add((key,'duplicate_identity'))
        if row.get('id'):seen.add(row['id'])
        a,b=row.get('start'),row.get('end')
        if not all(finite(t) for t in (a,b)) or not 0<=a<=b<=duration+.05:
            faults.add((key,'row_bounds'))
        words=row.get('words') or []
        if words and ' '.join(w.get('word','').strip() for w in words)!=' '.join(row.get('text','').split()):
            faults.add((key,'text_mismatch'))
        for wi,word in enumerate(words):
            x,y=word.get('start'),word.get('end')
            if not all(finite(t) for t in (x,y)) or not 0<=x<=y<=duration+.05:
                faults.add((key,wi,'word_bounds'));continue
            if y==x:continue # unlocated placeholders are reported, never invented
            if x<previous-1e-7:faults.add((key,wi,'overlap'))
            if all(finite(t) for t in (a,b)) and (x<a-1e-7 or y>b+1e-7):faults.add((key,wi,'outside_row'))
            previous=max(previous,y)
    return faults


def checked_refinement(rows,duration,name,operation,report):
    """Work on a copy. Optional model failures cannot partially alter the song.

    Cancellation inherits BaseException and intentionally propagates.
    """
    baseline=copy.deepcopy(rows);candidate=copy.deepcopy(rows)
    try:
        details=operation(candidate)
        old_ids=[r['id'] for r in baseline if r.get('id') and not is_music_label(r.get('text',''))]
        by_id={r.get('id'):r for r in candidate if r.get('id')}
        if [r.get('id') for r in candidate if r.get('id') in old_ids]!=old_ids:
            raise ValueError('Mevcut söz satırları silindi veya sırası değişti')
        for ri,old in enumerate(baseline):
            new=by_id.get(old.get('id')) if old.get('id') else candidate[ri] if ri<len(candidate) else None
            if new is None:raise ValueError('Mevcut satır kayboldu')
            if old.get('locked') and old!=new:raise ValueError('Kilitli satır değiştirildi')
            if not is_music_label(old.get('text','')) and old['text']!=new['text']:
                raise ValueError('Verilen sözler değiştirildi')
            for wi,word in enumerate(old.get('words') or []):
                if word.get('timing_source')=='manual' and (wi>=len(new.get('words') or []) or word!=new['words'][wi]):
                    raise ValueError('Elle bağlanan kelime değiştirildi')
        if structural_faults(candidate,duration)-structural_faults(baseline,duration):
            raise ValueError('Yeni zamanlama çakışması veya geçersiz sınır oluştu')
    except Exception as exc:
        report.setdefault('refinement_warnings',[]).append({'stage':name,'reason':str(exc)})
        return None
    rows[:]=candidate
    return details


def quality_report(rows,duration):
    missing=[];review=[];estimated=[]
    for ri,row in enumerate(rows):
        if is_music_label(row.get('text','')):continue
        words=row.get('words') or []
        if not words and row.get('text','').strip():missing.append({'row':ri+1,'word':None})
        for wi,w in enumerate(words):
            item={'row':ri+1,'word':wi+1}
            if not all(finite(w.get(k)) for k in ('start','end')) or w['end']<=w['start']:missing.append(item)
            if w.get('needs_review'):review.append(item)
            if w.get('timing_source') in ('estimated','repeat_inferred'):estimated.append(item)
    faults=structural_faults(rows,duration)
    try:render_errors=render_timing_issues(rows)
    except (ValueError,TypeError,KeyError):render_errors=['Geçersiz zamanlama verisi']
    return {'status':'needs_review' if missing or review or faults or render_errors else 'estimated' if estimated else 'ready',
            'missing_words':missing,'review_words':review,'estimated_words':estimated,
            'structural_errors':[list(x) for x in sorted(faults,key=str)],'render_errors':render_errors,
            'accuracy_guaranteed':False}
