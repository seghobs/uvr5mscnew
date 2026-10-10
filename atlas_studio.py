"""Complementary ensemble: preserve the mixture, never gate a vocal region.

V1 uses design weights; V2 uses a reference-calibrated expert mixture.
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
    expected = [(m['model_type'], m['model_key']) for m in preset['models']]
    if not all(isinstance(m, dict) for m in models) or [(m.get('model_type'), m.get('model_key')) for m in models] != expected:
        raise ValueError('Atlas Studio model listesi değişmiş. Preseti yeniden uygulayın.')
    if preset.get('frequency_weights') is not None:
        from atlas_band_ensemble import validate_frequency_weights
        validate_frequency_weights(preset['frequency_weights'],len(preset['models']))


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


def run_atlas_studio(core, source, models, out_format, output_dir, progress, preset=PRESET):
    validate_models(models, preset)
    name = preset['name']
    count = len(preset['models'])
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
        estimates = []
        for index, model in enumerate(preset['models']):
            progress(index / count * .9, f"{name} {index + 1}/{count}: {model['model_key']}")
            try:
                files = core.roformer_separator(str(prepared), model['model_key'], 'wav',
                    256, False, 8, 1, 1.0, 0.0, '', work_dir=str(work),
                    overlap_factor=8, float_output=True,
                    progress_callback=lambda p, m, i=index: progress((i + p) / count * .9, f'{name} {i + 1}/{count} · {m}'))
                pair = {}
                for file in files:
                    kind = classify_stem(file)
                    if kind in pair:
                        raise ValueError('Model aynı kanalı iki kez üretti')
                    info = sf.info(file)
                    if info.samplerate != rate or info.channels != 2 or info.frames != processing_frames:
                        raise ValueError('Model çıktısının süresi veya kanal yapısı kaynakla uyuşmuyor')
                    pair[kind] = file
                if set(pair) != {'vocal', 'inst'}:
                    raise ValueError('Model vokal ve enstrümanı birlikte üretmedi')
                estimate, _ = sf.read(pair[model['estimate']], dtype='float64', always_2d=True)
                if np.max(np.abs(estimate)) >= .999:
                    raise ValueError('Model çıktısında tepe sınırına ulaşıldı; seviye korunamadı')
                estimates.append(estimate[:frames] / headroom)
            finally:
                core.clear_gpu_and_ram_cache()
        progress(.94, f'{name}: '+('frekanslara göre ses kanalları birleştiriliyor' if preset.get('frequency_weights') is not None
            else 'iki kanalın toplamı kaynakla korunuyor'))
        vocal, instrumental = combine(source_wave, estimates, preset)
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
