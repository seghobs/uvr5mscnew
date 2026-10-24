"""Smooth frequency-dependent expert weights; complementary source is untouched."""
import numpy as np
from scipy.signal import stft, istft

RATE=44100
FFT=2048
HOP=512


def validate_frequency_weights(spec, count):
    anchors=np.asarray(spec['anchors_hz'],dtype=float)
    weights=np.asarray(spec['weights'],dtype=float)
    if (anchors.ndim!=1 or len(anchors)<2 or anchors[0]!=0 or anchors[-1]!=RATE/2
            or not np.isfinite(anchors).all() or (np.diff(anchors)<=0).any()
            or weights.shape!=(count,len(anchors)) or not np.isfinite(weights).all()
            or (weights<0).any() or not np.allclose(weights.sum(axis=0),1,atol=1e-8,rtol=0)):
        raise ValueError('Frekans karışımı ayarları geçersiz')
    return anchors,weights


def frequency_matrix(spec,count,frequencies):
    anchors,weights=validate_frequency_weights(spec,count)
    return np.stack([np.interp(frequencies,anchors,row) for row in weights])


def spectrum(wave):
    if len(wave)<FFT:
        wave=np.pad(wave,((0,FFT-len(wave)),(0,0)))
    return stft(wave.T,fs=RATE,nperseg=FFT,noverlap=FFT-HOP,boundary='zeros',padded=True)[2]


def _combine_frequency_block(source,candidates,spec):
    """Shared timebase/gain. No masks, gating, peak limiting or region replacement."""
    if source.ndim!=2 or source.shape[1]!=2 or not len(source) or not np.isfinite(source).all():
        raise ValueError('Kaynak ses geçersiz')
    frequencies=np.fft.rfftfreq(FFT,1/RATE)
    weights=frequency_matrix(spec,len(candidates),frequencies)
    merged=None
    for i,candidate in enumerate(candidates):
        if candidate.shape!=source.shape or not np.isfinite(candidate).all():
            raise ValueError('Model çıktısı kaynakla uyuşmuyor')
        transformed=spectrum(candidate)
        if merged is None:merged=np.zeros_like(transformed)
        merged+=transformed*weights[i][None,:,None]
    _,wave=istft(merged,fs=RATE,nperseg=FFT,noverlap=FFT-HOP,input_onesided=True,boundary=True)
    vocal=wave.T[:len(source)]
    if vocal.shape!=source.shape or not np.isfinite(vocal).all():
        raise ValueError('Frekans karışımı geçersiz çıktı üretti')
    return vocal,source-vocal


def combine_frequency(source,candidates,spec):
    """Bound STFT memory; aligned overlap reproduces the full-record transform."""
    validate_frequency_weights(spec,len(candidates))
    if (source.ndim!=2 or source.shape[1]!=2 or not len(source) or not np.isfinite(source).all()
            or any(x.shape!=source.shape or not np.isfinite(x).all() for x in candidates)):
        raise ValueError('Kaynak veya model çıktısı geçersiz')
    block=262144  # Multiple of HOP; FFT context covers every contributing frame.
    if len(source)<=block:return _combine_frequency_block(source,candidates,spec)
    vocal=np.empty(source.shape,dtype=np.float64)
    for start in range(0,len(source),block):
        stop=min(len(source),start+block)
        left=max(0,start-FFT);right=min(len(source),stop+FFT)
        part,_=_combine_frequency_block(source[left:right],[x[left:right] for x in candidates],spec)
        vocal[start:stop]=part[start-left:stop-left]
    return vocal,source-vocal
