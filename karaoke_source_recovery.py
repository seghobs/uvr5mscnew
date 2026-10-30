"""Recover missing provenance only when the complete stem sum matches a file."""
from pathlib import Path
import hashlib
import math


def verified_original(vocal_path,instrumental_path,roots,progress=lambda *args:None):
    """No title matching, network search, resampling, or guessed time offsets."""
    import numpy as np
    import soundfile as sf
    if not instrumental_path:return None
    try:
        vi,ii=sf.info(str(vocal_path)),sf.info(str(instrumental_path))
        shape=lambda info:(info.frames,info.samplerate,info.channels)
        if shape(vi)!=shape(ii) or vi.frames<vi.samplerate:return None
        candidates=set()
        for root in roots:
            directory=Path(root).resolve()
            if directory.is_dir():
                candidates.update(p.resolve() for p in directory.iterdir() if p.is_file()
                    and p.suffix.lower() in ('.wav','.flac','.ogg','.mp3') and p.resolve().is_relative_to(directory))
        excluded={Path(vocal_path).resolve(),Path(instrumental_path).resolve()}
        matches=[]
        with sf.SoundFile(str(vocal_path)) as vocal,sf.SoundFile(str(instrumental_path)) as music:
            windows=[]
            for fraction in (.15,.5,.85):
                position=min(vi.frames-vi.samplerate,max(0,round(vi.frames*fraction)))
                vocal.seek(position);music.seek(position)
                windows.append((position,vocal.read(vi.samplerate,dtype='float64',always_2d=True)
                    +music.read(vi.samplerate,dtype='float64',always_2d=True)))
            if sum(float(np.sum(a*a)) for _,a in windows)<1e-6:return None
            for path in sorted(candidates-excluded):
                try:
                    info=sf.info(str(path))
                    if shape(info)!=shape(vi):continue
                    progress(.99,'Orijinal sesin zaman çizgisi ve ayrıştırma toplamı doğrulanıyor…')
                    with sf.SoundFile(str(path)) as source:
                        valid=True
                        for position,expected in windows:
                            source.seek(position);actual=source.read(len(expected),dtype='float64',always_2d=True)
                            if np.sum((actual-expected)**2)>1e-6*max(1e-12,np.sum(expected**2)):
                                valid=False;break
                        if not valid:continue
                        source.seek(0);vocal.seek(0);music.seek(0)
                        energy=error=0.;digest=hashlib.sha256()
                        while source.tell()<source.frames:
                            actual=source.read(65536,dtype='float64',always_2d=True)
                            expected=vocal.read(len(actual),dtype='float64',always_2d=True)+music.read(
                                len(actual),dtype='float64',always_2d=True)
                            if actual.shape!=expected.shape:valid=False;break
                            delta=actual-expected
                            # A local edit must not disappear in the average
                            # error of a long recording. Allow PCM rounding,
                            # never a changed sample hidden by the rest.
                            if np.max(np.abs(delta))>1e-4:valid=False;break
                            energy+=float(np.sum(expected**2));error+=float(np.sum(delta**2))
                            digest.update(actual.astype('<f4').tobytes())
                        if valid and math.isfinite(error) and energy>1e-6 and error/energy<=1e-6:
                            matches.append((path,digest.hexdigest()))
                except (OSError,RuntimeError,ValueError):continue
        # Identical decoded audio with different tags is the same time base.
        if matches and len({digest for _,digest in matches})==1:return matches[0][0]
    except (OSError,RuntimeError,ValueError):pass
    return None
