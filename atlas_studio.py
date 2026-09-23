"""Complementary ensemble: preserve the mixture, never gate a vocal region.

Weights are conservative design choices, not fitted benchmark scores. Mixture
consistency does not prove the content was assigned to the correct stem.
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


def roformer_step_seconds(config, factor):
    """audio-separator 0.32 Roformer takes hop seconds, not overlap count."""
    if factor < 1:
        raise ValueError('Örtüşme katsayısı en az 1 olmalı')
    frames = int(config.audio.hop_length) * (int(config.inference.dim_t) - 1)
    rate = int(config.audio.sample_rate)
    if frames <= 0 or rate <= 0:
        raise ValueError('Model pencere ayarları geçersiz')
    return max(1, frames // factor) / rate


def validate_models(models):
    expected = [(m['model_type'], m['model_key']) for m in PRESET['models']]
    if not all(isinstance(m, dict) for m in models) or [(m.get('model_type'), m.get('model_key')) for m in models] != expected:
        raise ValueError('Atlas Studio model listesi değişmiş. Preseti yeniden uygulayın.')


def combine(source, estimates):
    """All estimates have the same timebase and gain as source (frames, channels)."""
    if len(estimates) != len(PRESET['models']):
        raise ValueError('Atlas Studio için üç model çıktısı gerekli')
    if not np.isfinite(source).all():
        raise ValueError('Kaynak ses geçersiz örnekler içeriyor')
    vocal = np.zeros_like(source, dtype=np.float64)
    for estimate, model in zip(estimates, PRESET['models']):
        if estimate.shape != source.shape or not np.isfinite(estimate).all():
            raise ValueError('Model çıktısı kaynakla uyuşmuyor')
        candidate = source - estimate if model['estimate'] == 'inst' else estimate
        vocal += model['weight'] * candidate
    return vocal, source - vocal


def run_atlas_studio(core, source, models, out_format, output_dir, progress):
    validate_models(models)
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
        for index, model in enumerate(PRESET['models']):
            progress(index / 3 * .9, f"Atlas Studio {index + 1}/3: {model['model_key']}")
            try:
                files = core.roformer_separator(str(prepared), model['model_key'], 'wav',
                    256, False, 8, 1, 1.0, 0.0, '', work_dir=str(work),
                    overlap_factor=8, float_output=True,
                    progress_callback=lambda p, m, i=index: progress((i + p) / 3 * .9, f'Atlas Studio {i + 1}/3 · {m}'))
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
        progress(.94, 'Atlas Studio: iki kanalın toplamı kaynakla korunuyor')
        vocal, instrumental = combine(source_wave, estimates)
        gain = 1.0
        if out_format == 'flac':
            # One common gain only: no clipping, independent limiting or gates.
            peak = max(float(np.max(np.abs(vocal))), float(np.max(np.abs(instrumental))))
            gain = min(1.0, .999 / max(peak, .999))
        for label, wave in [('Vocals', vocal), ('Instrumental', instrumental)]:
            filename = f'AtlasStudio_{label}_{token}.{out_format}'
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
        progress(1.0, 'Atlas Studio tamamlandı' +
            (f' · Taşmayı önlemek için iki kanal birlikte {20 * np.log10(gain):.2f} dB azaltıldı' if gain < 1 else ''))
    return [str(path) for path in outputs]
