"""Real whole-song API validation. Never save or overwrite the user's lyrics."""
import copy
import json
import math
import os
from pathlib import Path
import time
import uuid
import requests
from karaoke_supplied_alignment import instrumental,spoken
from karaoke_timing import render_windows,solo_windows

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'cache/supplied_ten'


def verify(before,result,duration):
    rows=result['segments'];report=result['alignment_report']
    sung=[r for r in rows if not instrumental(r)]
    assert [r['text'] for r in sung]==[r['text'] for r in before],'Supplied text/order changed'
    expected=sum(spoken(t) for r in before for t in r['text'].split())
    assert report['linked_words']==report['target_words']==expected,'Unbound word'
    previous=0.
    for row in rows:
        assert math.isfinite(row['start']) and math.isfinite(row['end'])
        assert 0<=row['start']<row['end']<=duration,'Row outside audio'
        assert row['start']>=previous-1e-6,'Rows overlap'
        previous=row['end']
        assert [w['word'] for w in row['words']]==row['text'].split(),'Word occurrence lost'
        for word in row['words']:
            if spoken(word['word']):assert row['start']<=word['start']<word['end']<=row['end']
    assert report['music_evidence_available'],'Accompaniment missing'
    assert report['solo_count']>=1,'No verified music interval'
    for row,end in render_windows(rows):
        if instrumental(row):assert end==row['end'],'Video extends SOLO beyond measured end'
    assert solo_windows(rows,duration)==[],'Video invents unchecked music gaps'
    return {'word_count':expected,'solo_count':report['solo_count'],'review_rows':len(report['review_rows']),
        'supplied_text_preserved':True,'all_words_bound':True,'times_ordered_in_audio':True,
        'solo_display_end_exact':True,'no_unverified_video_gap_labels':True}


def verify_acoustic_solos(identifier,result):
    # Independently recorded detector output from the prior full-audio pass.
    # This is an acoustic proxy, not human-annotated timing ground truth.
    evidence=json.loads((WORK/(identifier+'-diagnostics.json')).read_text(encoding='utf8'))
    for solo in result['alignment_report']['solo_intervals']:
        a,b=solo['start'],solo['end']
        assert all(b<=va or a>=vb for va,vb in evidence['voice_regions']),'SOLO intersects detected voice'
        covered=sum(max(0,min(b,mb)-max(a,ma)) for ma,mb in evidence['music_regions'])
        assert covered>=b-a-1e-6,'SOLO outside accompaniment activity'
    return {'no_solo_over_detected_voice':True,'solo_inside_detected_accompaniment':True}


def main():
    manifest=json.loads((WORK/'manifest.json').read_text(encoding='utf8'))
    if len(manifest)!=10:raise ValueError('Exactly ten recordings required')
    session=requests.Session();session.trust_env=False
    folder=ROOT/'uploads/.supplied-tests';folder.mkdir(exist_ok=True)
    run=uuid.uuid4().hex[:8];results=[]
    for track in manifest:
        source=Path(track['file']);link=folder/f'{run}_{track["id"]}{source.suffix}'
        if not link.resolve().is_relative_to(ROOT/'uploads'):raise ValueError('Unsafe test path')
        os.link(source,link)
        rows=[copy.deepcopy(r) for r in track['rows'] if not instrumental(r)]
        for row in rows:row.update(start=0,end=0,words=[],locked=False)
        started=time.monotonic()
        try:
            response=session.post('http://127.0.0.1:3000/api/lyrics/align-supplied',json={
                'file_name':str(link),'instrumental_file_name':str(source.with_name(source.name.replace('_Vocals_','_Instrumental_'))),
                'segments':rows,'language':'tr'},timeout=30)
            response.raise_for_status();task=response.json()['task_id']
            progress=0.;deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                time.sleep(.5);status=session.get('http://127.0.0.1:3000/status/'+task,timeout=30)
                status.raise_for_status();data=status.json()
                current=data.get('progress',0)
                assert current>=progress,'Progress moved backwards';progress=current
                if data['status']=='failed':raise RuntimeError(data.get('error'))
                if data['status']=='completed':break
            else:raise TimeoutError('Whole-song task exceeded three minutes')
            result=data['result'];checks=verify(rows,result,track['duration'])
            checks.update(verify_acoustic_solos(track['id'],result))
            # Round-trip the timed result through the same production endpoint.
            # Generated labels must not multiply on a second explicit click.
            repeat=session.post('http://127.0.0.1:3000/api/lyrics/align-supplied',json={
                'file_name':str(link),'instrumental_file_name':str(source.with_name(source.name.replace('_Vocals_','_Instrumental_'))),
                'segments':result['segments'],'language':'tr'},timeout=30)
            repeat.raise_for_status();repeat_task=repeat.json()['task_id'];deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                time.sleep(.5);repeat_status=session.get('http://127.0.0.1:3000/status/'+repeat_task,timeout=30)
                repeat_status.raise_for_status();repeated=repeat_status.json()
                if repeated['status']=='failed':raise RuntimeError(repeated.get('error'))
                if repeated['status']=='completed':break
            else:raise TimeoutError('Repeat task timed out')
            verify(rows,repeated['result'],track['duration'])
            assert repeated['result']['alignment_report']['solo_intervals']==result['alignment_report']['solo_intervals'],'Repeat changed/duplicated labels'
            checks['repeat_labels_identical']=True
            (WORK/(track['id']+'-api-result.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
            results.append({'id':track['id'],'duration':track['duration'],'seconds':time.monotonic()-started,
                'passed':True,'checks':checks,'solo_intervals':result['alignment_report']['solo_intervals']})
            print('PASS',track['id'],checks,flush=True)
        except Exception as exc:
            results.append({'id':track['id'],'passed':False,'error':str(exc)})
            print('FAIL',track['id'],str(exc),flush=True)
        finally:
            if link.exists() and os.path.samefile(link,source):link.unlink()
            (WORK/'web-validation.json').write_text(json.dumps({'recordings':results,
                'passed':sum(r['passed'] for r in results),'total':10},ensure_ascii=False,indent=2),encoding='utf8')
    if not all(r['passed'] for r in results):raise RuntimeError('One or more real-song checks failed')


if __name__=='__main__':main()
