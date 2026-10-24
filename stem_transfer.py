"""Immutable, sample-aligned transfer between a matched stem pair."""
from pathlib import Path
import math
import uuid
import numpy as np
import soundfile as sf


def transfer_pair(root,vocal_name,instrumental_name,start,end,amount=1.):
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
    vocal,sr=sf.read(paths[0],dtype='float32',always_2d=True)
    inst,other_sr=sf.read(paths[1],dtype='float32',always_2d=True)
    if sr!=other_sr or vocal.shape!=inst.shape or not np.isfinite(vocal).all() or not np.isfinite(inst).all():
        raise ValueError('Kanalların örnekleme hızı, süresi ve kanal sayısı aynı olmalı')
    if end>len(vocal)/sr+1e-9:raise ValueError('Seçim ses süresini aşıyor')
    first,last=round(start*sr),round(end*sr)
    if last<=first:raise ValueError('Seçilen aralık çok kısa')
    envelope=np.ones(last-first,dtype='float32')*amount
    fade=min(round(sr*.005),len(envelope)//2)
    if fade:
        ramp=np.linspace(0,1,fade,dtype='float32')
        envelope[:fade]*=ramp;envelope[-fade:]*=ramp[::-1]
    moved=vocal[first:last]*envelope[:,None]
    vocal[first:last]-=moved;inst[first:last]+=moved
    token=uuid.uuid4().hex[:12]
    outputs=[root/f'Transfer_Vocals_{token}.wav',root/f'Transfer_Instrumental_{token}.wav']
    try:
        for path,wave in zip(outputs,(vocal,inst)):sf.write(path,wave,sr,subtype='FLOAT')
    except BaseException:
        for path in outputs:path.unlink(missing_ok=True)
        raise
    return {'vocal':outputs[0].name,'instrumental':outputs[1].name,'start':first/sr,'end':last/sr,'sample_rate':sr,'frames':len(vocal)}
