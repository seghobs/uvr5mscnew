"""Conservative same-recording repeat detection; never generate new lyric text."""
import copy
import hashlib
import numpy as np


def expand_repeats(rows,audio_path,verifier=None):
    import soundfile as sf
    from scipy.signal import resample_poly,fftconvolve,find_peaks,stft
    from math import gcd
    from karaoke_supplied_alignment import instrumental,protected,alignment_mono
    audio,rate=sf.read(str(audio_path),dtype='float32',always_2d=True)
    divisor=gcd(rate,2000)
    wave=resample_poly(alignment_mono(audio),2000//divisor,rate//divisor).astype('float64')
    wave-=wave.mean()
    _,times,spectrum=stft(wave,fs=2000,nperseg=128,noverlap=88)
    features=np.log1p(np.abs(spectrum[2:60])*100)
    features-=features.mean(axis=0,keepdims=True)
    features/=np.maximum(np.linalg.norm(features,axis=0,keepdims=True),1e-8)
    occupied=[(r['start'],r['end']) for r in rows if not instrumental(r) and r['end']>r['start']]
    added=[];seen=set();tested=0
    for row in rows:
        if len(rows)+len(added)>=500:break
        words=row.get('words') or []
        if not row.get('id') or instrumental(row) or protected(row) or len(row['text'].split())<2:continue
        if not words or any(w.get('probability',0)<.15 or w['end']<=w['start'] for w in words):continue
        if sum(w.get('probability',0) for w in words)/len(words)<.5:continue
        a,b=row['start'],row['end'];n=round((b-a)*2000)
        if n<2400 or n>40000:continue
        template=wave[round(a*2000):round(a*2000)+n]
        if len(template)!=n:continue
        template=template-template.mean();energy=float(template@template)
        if energy<1e-8:continue
        tested+=1
        dot=fftconvolve(wave,template[::-1],mode='valid')
        sums=np.concatenate(([0.],np.cumsum(wave)));squares=np.concatenate(([0.],np.cumsum(wave*wave)))
        local=np.maximum(0,squares[n:]-squares[:-n]-(sums[n:]-sums[:-n])**2/n)
        similarity=dot/np.sqrt(np.maximum(local*energy,1e-20))
        peaks,_=find_peaks(similarity,height=.97,distance=n)
        candidates=[(int(peak),True) for peak in peaks]
        if verifier is not None:
            first=round(a/.02);frames=round((b-a)/.02)
            pattern=features[:,first:first+frames]
            if frames>20 and pattern.shape[1]==frames:
                similarity_mel=sum(fftconvolve(channel,part[::-1],mode='valid') for channel,part in zip(features,pattern))/frames
                mel_peaks,_=find_peaks(similarity_mel,height=.80,distance=frames)
                candidates.extend((int(peak*40),False) for peak in mel_peaks)
        candidates=sorted(candidates,key=lambda x:x[0])
        for peak,exact in candidates:
            start=peak/2000;end=start+n/2000
            if abs(start-a)<.2 or any(start<y+.12 and end>x-.12 for x,y in occupied):continue
            # Three separate portions must agree: an instrumental motif alone cannot approve a line.
            candidate=wave[peak:peak+n]
            scores=[]
            for part in np.array_split(np.arange(n),3):
                x=template[part];y=candidate[part];y=y-y.mean();x=x-x.mean()
                scores.append(float(x@y/np.sqrt(max(float(x@x)*float(y@y),1e-20))))
            if exact and min(scores)<.95:continue
            verified=None
            if not exact:
                verified=verifier(row,start,end)
                if verified is None:continue
                start=verified[0]['start'];end=verified[-1]['end']
                if not (0<=start<end<=len(wave)/2000):continue
                if any(start<y+.12 and end>x-.12 for x,y in occupied):continue
            key=(round(start,2),round(end,2))
            if key in seen:continue
            seen.add(key);occupied.append((start,end))
            duplicate=copy.deepcopy(row);delta=start-a
            duplicate.update(id='auto-repeat:'+hashlib.sha256((str(row.get('id'))+str(key)).encode()).hexdigest()[:16],
                             repeat_source_id=row.get('id'),start=start,end=end,locked=False)
            if verified is not None:
                duplicate['words']=verified
                duplicate['start']=verified[0]['start'];duplicate['end']=verified[-1]['end']
            else:
                for word in duplicate['words']:
                    word['start']+=delta;word['end']+=delta
            added.append(duplicate)
    # Never reorder supplied rows, including deliberately repeated verses.
    result=copy.deepcopy(rows)
    for row in sorted(added,key=lambda r:r['start']):
        index=next((i for i,r in enumerate(result) if r['start']>row['start']),len(result))
        result.insert(index,row)
    return result,{'repeated_rows_added':len(added),'repeat_templates_checked':tested,
                   'repeat_method':'acoustic_repeat_with_supplied_text_verification','repeat_accuracy_guaranteed':False}
