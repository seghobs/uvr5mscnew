"""Immutable, sample-aligned transfer between a matched stem pair."""
from pathlib import Path
import math
import uuid
import numpy as np
import soundfile as sf


def band_filters(low,high,rate):
    """RBJ biquads, matching Web Audio highpass/lowpass with Q = 1/sqrt(2)."""
    rows=[]
    for kind,frequency in [('highpass',low),('lowpass',high)]:
        omega=2*np.pi*frequency/rate;c=np.cos(omega);alpha=np.sin(omega)/(2*math.sqrt(.5))
        if kind=='highpass':b=[(1+c)/2,-(1+c),(1+c)/2]
        else:b=[(1-c)/2,1-c,(1-c)/2]
        rows.append([x/(1+alpha) for x in b]+[1,-2*c/(1+alpha),(1-alpha)/(1+alpha)])
    return np.asarray(rows)


def transfer_pair(root,vocal_name,instrumental_name,start,end,amount=1.,frequency_low=None,frequency_high=None,scope='selected'):
    root=Path(root).resolve()
    paths=[]
    for name in (vocal_name,instrumental_name):
        path=(root/name).resolve()
        if not path.is_relative_to(root) or path.parent!=root or not path.is_file():
            raise ValueError('Ses dosyası bulunamadı veya geçersiz')
        paths.append(path)
    if paths[0]==paths[1]:raise ValueError('İki farklı kanal seçin')
    if not all(math.isfinite(x) for x in (start,end,amount)) or not 0<=start<end or not 0<amount<=1:
        raise ValueError('Geçerli bir zaman aralığı ve aktarım miktarı seçin')
    vinfo,iinfo=map(sf.info,paths);sr=vinfo.samplerate
    if sr!=iinfo.samplerate or vinfo.frames!=iinfo.frames or vinfo.channels!=iinfo.channels:
        raise ValueError('Kanalların örnekleme hızı, süresi ve kanal sayısı aynı olmalı')
    if end>vinfo.frames/sr+1e-9:raise ValueError('Seçim ses süresini aşıyor')
    if scope not in ('selected','all'):raise ValueError('Geçersiz uygulama alanı')
    filtered=frequency_low is not None or frequency_high is not None
    if filtered and (frequency_low is None or frequency_high is None or not all(math.isfinite(f) for f in (frequency_low,frequency_high)) or not 20<=frequency_low<frequency_high<sr/2):
        raise ValueError('Frekans sınırları 20 Hz ile dosyanın Nyquist frekansı arasında olmalı')
    first,last=(0,vinfo.frames) if scope=='all' else (round(start*sr),round(end*sr))
    if last<=first:raise ValueError('Seçilen aralık çok kısa')
    fade=min(round(sr*.005),(last-first)//2)
    if filtered:
        from scipy.signal import sosfilt
        sos=band_filters(frequency_low,frequency_high,sr)
        state=np.zeros((2,2,vinfo.channels))
    token=uuid.uuid4().hex[:12]
    outputs=[root/f'Transfer_Vocals_{token}.wav',root/f'Transfer_Instrumental_{token}.wav']
    try:
        # Stream the export: full-song application does not allocate full-song buffers.
        with sf.SoundFile(paths[0]) as vin,sf.SoundFile(paths[1]) as iin, \
                sf.SoundFile(outputs[0],'w',samplerate=sr,channels=vinfo.channels,subtype='FLOAT') as vout, \
                sf.SoundFile(outputs[1],'w',samplerate=sr,channels=vinfo.channels,subtype='FLOAT') as iout:
            position=0
            while position<vinfo.frames:
                vocal=vin.read(65536,dtype='float32',always_2d=True)
                inst=iin.read(len(vocal),dtype='float32',always_2d=True)
                if not np.isfinite(vocal).all() or not np.isfinite(inst).all():raise ValueError('Ses dosyası geçersiz örnek içeriyor')
                a,b=max(first-position,0),min(last-position,len(vocal))
                if b>a:
                    moved=vocal[a:b].astype('float64')
                    if filtered:moved,state=sosfilt(sos,moved,axis=0,zi=state)
                    envelope=np.ones(b-a)*amount
                    if fade>1:
                        indices=np.arange(position+a-first,position+b-first)
                        envelope*=np.minimum(1,np.minimum(indices,(last-first-1)-indices)/(fade-1))
                    moved*=envelope[:,None]
                    vocal[a:b]-=moved;inst[a:b]+=moved
                vout.write(vocal);iout.write(inst);position+=len(vocal)
    except BaseException:
        for path in outputs:path.unlink(missing_ok=True)
        raise
    return {'vocal':outputs[0].name,'instrumental':outputs[1].name,'start':first/sr,'end':last/sr,'sample_rate':sr,'frames':vinfo.frames,'scope':scope}
