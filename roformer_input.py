"""Scope short-input padding to one Roformer instance and retain original duration."""
import numpy as np


def attach_minimum_window(instance):
    if not getattr(instance,'is_roformer',False):return None
    cfg=instance.model_data_cfgdict
    segment=instance.segment_size if instance.override_model_segment_size else cfg.inference.dim_t
    minimum=int(cfg.audio.hop_length)*(int(segment)-1)
    if minimum<=0:raise ValueError('Model penceresi geçersiz')
    original=instance.demix
    def padded_demix(mix):
        if mix.ndim!=2 or mix.shape[0]!=2 or not mix.shape[1] or not np.isfinite(mix).all():
            raise ValueError('Model girdisi geçerli stereo ses olmalı')
        frames=mix.shape[-1]
        if frames>=minimum:return original(mix)
        # The dependency's tail overlap-add assumes a complete native window.
        # Zero padding supplies context; only original frames leave this wrapper.
        result=original(np.pad(mix,((0,0),(0,minimum-frames))))
        if isinstance(result,dict):return {k:v[..., :frames] for k,v in result.items()}
        return result[..., :frames]
    instance.demix=padded_demix
    return minimum
