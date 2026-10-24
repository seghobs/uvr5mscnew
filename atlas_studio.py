"""Complementary ensemble: preserve the mixture, never gate a vocal region.

V1 uses design weights; V2 adds optional activity-protected residual vocal control.
Mixture consistency does not prove correct assignment or unseen-song superiority.
"""
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf
from studio_pro import classify_stem

PRESET = json.loads((Path(__file__).parent / 'frontend/src/lib/atlas-studio-preset.json').read_text(encoding='utf8'))
PRESET_V2 = json.loads((Path(__file__).parent / 'frontend/src/lib/atlas-studio-v2-preset.json').read_text(encoding='utf8'))


def inference_passes(preset):
    passes=preset.get('inference_passes',[{'transform':'identity','weight':1.0}])
    if (not passes or passes[0].get('transform')!='identity'
            or any(p.get('transform') not in ('identity','swap_channels','invert_polarity')
                   or not np.isfinite(p.get('weight',np.nan)) or p['weight']<=0 for p in passes)
            or len({p['transform'] for p in passes})!=len(passes)
            or not np.isclose(sum(p['weight'] for p in passes),1.0)):
        raise ValueError('Atlas çıkarım geçişleri geçersiz')
    return passes


def transform_audio(wave, transform):
    """Each transform is its own inverse; preserve timebase and stereo phase."""
    if transform=='identity':return wave
    if transform=='swap_channels':return wave[:, ::-1]
    if transform=='invert_polarity':return -wave
    raise ValueError('Bilinmeyen ses dönüşümü')


def roformer_step_seconds(config, factor):
    """audio-separator 0.32 Roformer takes hop seconds, not overlap count."""
    if factor < 1:
        raise ValueError('Örtüşme katsayısı en az 1 olmalı')
    frames = int(config.audio.hop_length) * (int(config.inference.dim_t) - 1)
    rate = int(config.audio.sample_rate)
    if frames <= 0 or rate <= 0:
        raise ValueError('Model pencere ayarları geçersiz')
    return max(1, frames // factor) / rate


def validate_models(models, preset=PRESET):
    inference_passes(preset)
    expected = [(m['model_type'], m['model_key']) for m in preset['models']]
    if not all(isinstance(m, dict) for m in models) or [(m.get('model_type'), m.get('model_key')) for m in models] != expected:
        raise ValueError('Atlas Studio model listesi değişmiş. Preseti yeniden uygulayın.')
    validate_cleanup(preset)
    if preset.get('frequency_weights') is not None:
        from atlas_band_ensemble import validate_frequency_weights
        validate_frequency_weights(preset['frequency_weights'],len(preset['models']))


def validate_cleanup(preset):
    config=preset.get('residual_cleanup')
    if config is None:return None
    if not isinstance(config,dict):raise ValueError('Artık vokal ayarı geçersiz')
    model=next((m for m in preset['models'] if m['model_key']==config.get('model_key') and m['estimate']=='vocal'),None)
    strength=config.get('strength')
    if model is None or not isinstance(strength,(int,float)) or not np.isfinite(strength) or not 0<strength<=1:
        raise ValueError('Artık vokal kontrolü mevcut bir vokal modelini ve 0–1 arası kuvveti gerektiriyor')
    reference=config.get('voice_reference_model_key')
    if reference is not None and not any(m['model_key']==reference and m['estimate']=='vocal' for m in preset['models']):
        raise ValueError('Vokal etkinliği mevcut bir vokal modelinden alınmalı')
    floor=config.get('activity_floor_db',-32.);full=config.get('activity_full_db',-18.)
    if not isinstance(floor,(int,float)) or not isinstance(full,(int,float)) or not np.isfinite([floor,full]).all() or not -100<=floor<full<=0:
        raise ValueError('Vokal etkinlik eşikleri geçersiz')
    return model


def combine(source, estimates, preset=PRESET):
    """All estimates have the same timebase and gain as source (frames, channels)."""
    if len(estimates) != len(preset['models']):
        raise ValueError(f"{preset['name']} için {len(preset['models'])} model çıktısı gerekli")
    if not np.isfinite(source).all():
        raise ValueError('Kaynak ses geçersiz örnekler içeriyor')
    frequency_spec=preset.get('frequency_weights')
    vocal = np.zeros_like(source, dtype=np.float64) if frequency_spec is None else None
    weights = [m['weight'] for m in preset['models']]
    if any(not np.isfinite(w) or w < 0 for w in weights) or not np.isclose(sum(weights), 1):
        raise ValueError('Model ağırlıkları geçersiz')
    candidates=[]
    for estimate, model in zip(estimates, preset['models']):
        if estimate.shape != source.shape or not np.isfinite(estimate).all():
            raise ValueError('Model çıktısı kaynakla uyuşmuyor')
        candidate = source - estimate if model['estimate'] == 'inst' else estimate
        candidates.append(candidate)
        if frequency_spec is None:vocal += model['weight'] * candidate
    if frequency_spec is not None:
        from atlas_band_ensemble import combine_frequency
        return combine_frequency(source,candidates,frequency_spec)
    return vocal, source - vocal


def run_model_estimate(core, prepared, model, work, rate, processing_frames, frames, headroom, progress):
    try:
        files=core.roformer_separator(str(prepared),model['model_key'],'wav',
            256,False,8,1,1.0,0.0,'',work_dir=str(work),overlap_factor=8,
            float_output=True,progress_callback=progress)
        pair={}
        for file in files:
            kind=classify_stem(file)
            if kind in pair:raise ValueError('Model aynı kanalı iki kez üretti')
            info=sf.info(file)
            if info.samplerate!=rate or info.channels!=2 or info.frames!=processing_frames:
                raise ValueError('Model çıktısının süresi veya kanal yapısı kaynakla uyuşmuyor')
            pair[kind]=file
        if set(pair)!={'vocal','inst'}:
            raise ValueError('Model vokal ve enstrümanı birlikte üretmedi')
        estimate,_=sf.read(pair[model['estimate']],dtype='float64',always_2d=True)
        if not np.isfinite(estimate).all():raise ValueError('Model çıktısı geçersiz örnekler içeriyor')
        if np.max(np.abs(estimate))>=.999:
            raise ValueError('Model çıktısında tepe sınırına ulaşıldı; seviye korunamadı')
        return estimate[:frames]/headroom
    finally:
        core.clear_gpu_and_ram_cache()


def run_atlas_studio(core, source, models, out_format, output_dir, progress, preset=PRESET):
    validate_models(models, preset)
    name = preset['name']
    count = len(preset['models'])
    passes = inference_passes(preset)
    total_passes = count * len(passes)
    cleanup_model=validate_cleanup(preset)
    inference_budget=.78 if cleanup_model else .9
    if out_format not in ('wav', 'flac'):
        raise ValueError('Atlas Studio için WAV veya FLAC seçin.')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:12]
    outputs = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    # Both models and partial exports stay private until the pair is complete.
    with tempfile.TemporaryDirectory(prefix='atlas_', dir=output_dir) as directory:
        work = Path(directory)
        decoded = work / 'source.wav'
        result = subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', str(source),
            '-ac', '2', '-ar', '44100', '-c:a', 'pcm_f32le', str(decoded)],
            capture_output=True, text=True, creationflags=flags)
        if result.returncode:
            raise RuntimeError(result.stderr[-1500:])
        source_wave, rate = sf.read(decoded, dtype='float64', always_2d=True)
        if not len(source_wave) or not np.isfinite(source_wave).all():
            raise ValueError('Kaynak ses boş veya geçersiz')
        frames = len(source_wave)
        # Headroom prevents per-stem peak normalization in the separator from
        # changing relative gains. Restore it before complementary combination.
        headroom = 0.25 / max(1.0, float(np.max(np.abs(source_wave))))
        prepared = work / 'atlas_input.wav'
        processing_frames = max(frames, 16 * rate)
        sf.write(prepared, np.pad(source_wave * headroom,
            ((0, processing_frames - frames), (0, 0))), rate, subtype='FLOAT')
        inputs={'identity':prepared}
        if len(passes)>1:
            prepared_wave,_=sf.read(prepared,dtype='float64',always_2d=True)
            for entry in passes[1:]:
                transform=entry['transform']
                inputs[transform]=work/f'atlas_{transform}.wav'
                sf.write(inputs[transform],transform_audio(prepared_wave,transform),rate,subtype='FLOAT')
        estimates = []
        for index, model in enumerate(preset['models']):
            averaged=None
            for pass_index, entry in enumerate(passes):
                offset=index*len(passes)+pass_index
                transform=entry['transform']
                progress(offset/total_passes*inference_budget,
                         f"{name} {index+1}/{count} · Geçiş {pass_index+1}/{len(passes)}: {model['model_key']}")
                estimate=run_model_estimate(core,inputs[transform],model,work,rate,
                    processing_frames,frames,headroom,
                    lambda p,m,o=offset:progress((o+p)/total_passes*inference_budget,f'{name} · {m}'))
                restored=transform_audio(estimate,transform)
                if averaged is None:averaged=entry['weight']*restored
                else:averaged+=entry['weight']*restored
            estimates.append(averaged)
        progress(inference_budget+.02, f'{name}: '+('frekanslara göre ses kanalları birleştiriliyor' if preset.get('frequency_weights') is not None
            else 'iki kanalın toplamı kaynakla korunuyor'))
        vocal, instrumental = combine(source_wave, estimates, preset)
        if cleanup_model:
            cleanup_headroom=.25/max(1.,float(np.max(np.abs(instrumental))))
            cleanup_input=work/'atlas_residual_input.wav'
            sf.write(cleanup_input,np.pad(instrumental*cleanup_headroom,
                ((0,processing_frames-frames),(0,0))),rate,subtype='FLOAT')
            residual=run_model_estimate(core,cleanup_input,cleanup_model,work,rate,
                processing_frames,frames,cleanup_headroom,
                lambda p,m:progress(.8+.16*p,f'{name} · Artık vokal kontrolü · {m}'))
            config=preset['residual_cleanup']
            reference=vocal
            if config.get('voice_reference_model_key'):
                reference=estimates[next(i for i,m in enumerate(preset['models']) if m['model_key']==config['voice_reference_model_key'])]
            from karaoke_residual import corrected_instrumental
            instrumental=corrected_instrumental(instrumental,residual,source_wave,reference,rate,
                strength=config['strength'],floor_db=config.get('activity_floor_db',-32.),full_db=config.get('activity_full_db',-18.))
            # Transfer the estimate into the vocal stem; no independent gain,
            # clipping, spectral gating, or deletion of the overall mixture.
            vocal=source_wave-instrumental
        gain = 1.0
        if out_format == 'flac':
            # One common gain only: no clipping, independent limiting or gates.
            peak = max(float(np.max(np.abs(vocal))), float(np.max(np.abs(instrumental))))
            gain = min(1.0, .999 / max(peak, .999))
        for label, wave in [('Vocals', vocal), ('Instrumental', instrumental)]:
            prefix = 'AtlasStudioV2' if preset['id'] == 'atlas_studio_v2' else 'AtlasStudio'
            filename = f'{prefix}_{label}_{token}.{out_format}'
            sf.write(work / filename, wave * gain, rate,
                subtype='FLOAT' if out_format == 'wav' else 'PCM_24')
            outputs.append(output_dir / filename)
        try:
            for target in outputs:
                os.replace(work / target.name, target)
        except Exception:
            for target in outputs:
                target.unlink(missing_ok=True)
            raise
        progress(1.0, f'{name} tamamlandı' +
            (f' · Taşmayı önlemek için iki kanal birlikte {20 * np.log10(gain):.2f} dB azaltıldı' if gain < 1 else ''))
    return [str(path) for path in outputs]
