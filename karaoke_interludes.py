"""Conservative music-only intervals; never infer a solo from a time gap alone."""
import copy
import hashlib
import math


def generated(row):
    from karaoke_supplied_alignment import instrumental
    return instrumental(row) and str(row.get('id') or '').startswith('auto-solo:') and not row.get('locked')


def regions(mask,step=.02,min_length=.12,bridge=.2):
    spans=[];start=None
    for i,value in enumerate([*mask,False]):
        if value and start is None:start=i
        if not value and start is not None:
            if (i-start)*step>=min_length:
                a,b=start*step,i*step
                if spans and a-spans[-1][1]<=bridge:spans[-1][1]=b
                else:spans.append([a,b])
            start=None
    return spans


def music_evidence(vocal_path,instrumental_path=None):
    import numpy as np
    import soundfile as sf
    from pathlib import Path
    vocal_path=Path(vocal_path)
    if instrumental_path is None:
        partner=vocal_path.with_name(vocal_path.name.replace('_Vocals_','_Instrumental_'))
        if partner==vocal_path or not partner.is_file():return [],[],False
        instrumental_path=partner
    a=sf.info(str(vocal_path));b=sf.info(str(instrumental_path))
    if abs(a.duration-b.duration)>.04:return [],[],False
    def envelope(path,keep=False):
        audio,rate=sf.read(str(path),dtype='float32',always_2d=True)
        # Power across channels does not cancel a stereo vocal.
        power=np.mean(audio**2,axis=1);hop=round(rate*.02)
        power=np.pad(power,(0,(-len(power))%hop))
        rms=np.sqrt(power.reshape(-1,hop).mean(axis=1))
        return (rms,audio,rate) if keep else rms
    vocal,audio,rate=envelope(vocal_path,True);music=envelope(instrumental_path)
    count=min(len(vocal),len(music));vocal=vocal[:count];music=music[:count]
    floor=max(1e-5,float(music.max(initial=0))*.005)
    music_mask=music>floor
    # Singing can produce CTC blanks during a held vowel. Its stem energy must
    # independently veto the label even when there is no character prediction.
    voice_mask=(vocal>np.maximum(music*.28,floor*2))
    voice=regions(voice_mask,min_length=.12,bridge=.25)
    # Independent speech-presence model adds a veto; it generates no lyrics.
    from faster_whisper.vad import get_speech_timestamps,VadOptions
    import torch
    import torchaudio.functional as AF
    from karaoke_supplied_alignment import alignment_mono
    wave=AF.resample(torch.from_numpy(alignment_mono(audio).copy()),rate,16000).numpy()
    for span in get_speech_timestamps(wave,VadOptions(threshold=.25,min_speech_duration_ms=150,
                                    min_silence_duration_ms=180,speech_pad_ms=80)):
        voice.append([span['start']/16000,span['end']/16000])
    return regions(music_mask,min_length=.25,bridge=.35),voice,True


def place_interludes(rows,duration,voice_regions,music_regions,evidence_available=True):
    from karaoke_supplied_alignment import instrumental
    rows=[r for r in rows if not generated(r)]
    if not evidence_available:
        return rows,{'solo_intervals':[],'solo_count':0,'unplaced_solo_ids':[],
            'music_evidence_available':False,'solo_policy':'accompaniment_required'}
    labels={};slot=0
    for row in rows:
        if instrumental(row) and not row.get('locked'):
            labels.setdefault(slot,[]).append(row)
        elif not instrumental(row):slot+=1
    base=[r for r in rows if not instrumental(r) or r.get('locked')]
    result=[];slot=0;inserted=[];unplaced=[]
    for i in range(len(base)+1):
        left=base[i-1] if i else None;right=base[i] if i<len(base) else None
        start=left['end'] if left else 0.;end=right['start'] if right else duration
        originals=labels.pop(slot,[])
        # A locked interlude already owns its interval; no second label beside it.
        eligible=not ((left and instrumental(left)) or (right and instrumental(right)))
        windows=[]
        if evidence_available and eligible and end>start:
            for ma,mb in music_regions:
                a,b=max(start,ma),min(end,mb)
                if b<=a:continue
                pieces=[(a,b)]
                for va,vb in voice_regions:
                    va=max(0,va-.12);vb=min(duration,vb+.20)
                    remaining=[]
                    for ca,cb in pieces:
                        if vb<=ca or va>=cb:remaining.append((ca,cb));continue
                        if ca<va:remaining.append((ca,min(cb,va)))
                        if cb>vb:remaining.append((max(ca,vb),cb))
                    pieces=remaining
                # Short intro captions are deliberate; sub-second fragments in
                # a long break flicker and do not establish a musical section.
                minimum=.4 if start==0 and end<4 else 3.
                windows.extend((ca,cb) for ca,cb in pieces if cb-ca>=minimum)
        if not evidence_available:
            # No accompaniment recording: preserve user labels, but don't invent
            # music from silence or an unverified vocal-only recording.
            result.extend(originals)
        else:
            if originals and not windows:unplaced.extend(r.get('id') for r in originals)
            for n,(a,b) in enumerate(windows):
                row=copy.deepcopy(originals[n]) if n<len(originals) else {
                    'id':'auto-solo:'+hashlib.sha256(f'{slot}:{a:.3f}:{b:.3f}'.encode()).hexdigest()[:16],
                    'text':'SOLO...','locked':False}
                row.update(start=a,end=b,words=[{'word':row['text'].strip(),'start':a,'end':b,
                    'timing_source':'manual','needs_review':False}])
                result.append(row);inserted.append({'start':a,'end':b,'id':row.get('id')})
        if right is not None:
            result.append(right)
            if not instrumental(right):slot+=1
    return result,{'solo_intervals':inserted,'solo_count':len(inserted),'unplaced_solo_ids':unplaced,
        'music_evidence_available':evidence_available,'solo_policy':'acoustic_vocal_veto_and_accompaniment_activity'}
