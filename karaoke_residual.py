"""Smooth activity on the correction only; never mute the instrumental itself."""
import numpy as np
from scipy.ndimage import maximum_filter1d,uniform_filter1d


def correction_activity(source,voice_reference,rate,floor_db=-32.,full_db=-18.):
    if (source.shape!=voice_reference.shape or source.ndim!=2 or not len(source)
            or not np.isfinite(source).all() or not np.isfinite(voice_reference).all()
            or rate<=0 or not np.isfinite([floor_db,full_db]).all() or floor_db>=full_db):
        raise ValueError('Vokal etkinlik referansı geçersiz')
    step=max(1,round(rate*.05));starts=np.arange(0,len(source),step)
    source_power=np.array([np.mean(source[start:start+step]**2) for start in starts])
    voice_power=np.array([np.mean(voice_reference[start:start+step]**2) for start in starts])
    ratio=10*np.log10((voice_power+1e-20)/(source_power+1e-20))
    activity=np.clip((ratio-floor_db)/(full_db-floor_db),0.,1.)
    activity[(source_power<1e-12)|(voice_power<1e-12)]=0.
    # Expand correction around detected voice, then soften transitions. This is
    # a gain on the removed estimate, not a gate on the musical output.
    activity=maximum_filter1d(activity,size=5,mode='nearest')
    activity=uniform_filter1d(activity,size=5,mode='nearest')
    centers=np.minimum(starts+step/2,len(source)-1)
    return np.interp(np.arange(len(source)),centers,activity)


def corrected_instrumental(instrumental,residual,source,voice_reference,rate,strength=1.,floor_db=-32.,full_db=-18.):
    if (instrumental.shape!=residual.shape or instrumental.shape!=source.shape
            or not np.isfinite(instrumental).all() or not np.isfinite(residual).all()
            or not np.isfinite(strength) or not 0<=strength<=1):
        raise ValueError('Artık vokal düzeltmesi geçersiz')
    activity=correction_activity(source,voice_reference,rate,floor_db,full_db)
    return instrumental-strength*activity[:,None]*residual
