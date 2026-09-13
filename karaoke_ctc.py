"""Turkish character alignment after coarse Whisper alignment.

Model: mpoyraz/wav2vec2-xls-r-300m-cv7-turkish (CC BY 4.0).
No duration splitting or repeated-word deduplication is performed.
"""
import copy
import json
import unicodedata
from pathlib import Path

MODEL_ID = 'mpoyraz/wav2vec2-xls-r-300m-cv7-turkish'
MODEL_REVISION = '708639f50559d7970f462e13ec64d3f059ca89f6'
MODEL_DIR = Path(__file__).resolve().parent / 'models/alignment/turkish-ctc'


def normalized_words(words, vocab):
    result = []
    for word in words:
        text = unicodedata.normalize('NFC', word['word']).replace('I', 'ı').replace('İ', 'i').lower()
        # Fold unsupported circumflexes only in the acoustic target, not lyrics.
        text = ''.join({'â':'a','î':'i','û':'u'}.get(c,c) if c not in vocab else c for c in text)
        text = ''.join(c for c in text if not unicodedata.category(c).startswith('P'))
        if not text or any(c not in vocab or c.isspace() for c in text):
            raise ValueError('Kelimenin tüm harfleri hizalama modelinde temsil edilemiyor.')
        result.append(text)
    return result


def words_from_spans(words, normalized, spans, targets, scale, offset, include_syllables=False):
    if [s.token for s in spans] != targets:
        raise ValueError('Harf hizalaması tüm tekrarları koruyamadı.')
    result, cursor = [], 0
    for original, text in zip(words, normalized):
        chars = spans[cursor:cursor + len(text)]
        cursor += len(text) + 1  # each occurrence consumes its OWN character spans
        score = sum(float(c.score) for c in chars) / len(chars)
        start, end = offset + chars[0].start * scale, offset + chars[-1].end * scale
        result.append({**original, 'start': start, 'end': end, 'probability': score,
                       'timing_source': 'ctc', 'needs_review': score < .5 or end <= start})
        if include_syllables:
            from karaoke_syllables import syllable_ranges
            result[-1]['syllables'] = [
                {'text': text[a:b], 'start': offset + chars[a].start * scale,
                 'end': offset + chars[b-1].end * scale,
                 'score': sum(float(c.score) for c in chars[a:b]) / (b-a)}
                for a, b in syllable_ranges(text)]
    return result


def refine_turkish(audio_path, segments, language, progress=None, include_syllables=False):
    if language != 'tr':
        return segments
    import soundfile as sf
    import torch
    import torchaudio.functional as AF
    from transformers import Wav2Vec2ForCTC, Wav2Vec2FeatureExtractor

    if not (MODEL_DIR / 'pytorch_model.bin').is_file():
        from huggingface_hub import snapshot_download
        if progress:
            progress(0, 'Türkçe harf hizalama modeli indiriliyor...')
        snapshot_download(MODEL_ID, revision=MODEL_REVISION, local_dir=str(MODEL_DIR),
                          allow_patterns=['config.json', 'preprocessor_config.json', 'vocab.json',
                                          'pytorch_model.bin', 'README.md'])
    vocab = json.loads((MODEL_DIR / 'vocab.json').read_text(encoding='utf-8'))
    device = 'cuda' if torch.cuda.is_available() and torch.cuda.mem_get_info()[0] > 3 * 1024**3 else 'cpu'
    model = Wav2Vec2ForCTC.from_pretrained(MODEL_DIR, local_files_only=True).eval().to(device)
    extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_DIR, local_files_only=True)
    result = copy.deepcopy(segments)
    info = sf.info(audio_path)
    # Align neighbouring lines together, so the same sound cannot be assigned
    # independently to the last word of one line and the first of the next.
    groups = []
    for segment in result:
        if not groups or segment['end'] - groups[-1][0]['start'] > 18:
            groups.append([])
        groups[-1].append(segment)
    boundaries = [(left[-1]['end'] + right[0]['start']) / 2 for left, right in zip(groups, groups[1:])]
    try:
        for index, group in enumerate(groups):
            if progress:
                progress(index / max(1, len(groups)), f'Harfler sesle eşleştiriliyor: {index + 1}/{len(groups)}')
            words = [w for segment in group for w in segment.get('words', [])]
            if not words:
                continue
            start = max(0, group[0]['start'] - .8)
            end = min(info.duration, group[-1]['end'] + .8)
            if index:
                start = max(start, boundaries[index - 1])
            if index < len(groups) - 1:
                end = min(end, boundaries[index])
            # A bad coarse segment must not trigger unbounded GPU allocation.
            if end <= start or end - start > 22:
                for word in words:
                    word['needs_review'] = True
                continue
            try:
                normalized = normalized_words(words, vocab)
                target_ids = [vocab[c] for c in '|'.join(normalized)]
            except ValueError:
                for word in words:
                    word['needs_review'] = True
                continue
            first_sample = int(start * info.samplerate)
            offset = first_sample / info.samplerate
            audio, rate = sf.read(audio_path, start=first_sample, stop=int(end * info.samplerate), dtype='float32')
            if audio.ndim == 2:
                audio = audio.mean(axis=1)
            wave = AF.resample(torch.from_numpy(audio), rate, 16000)
            inputs = extractor(wave.numpy(), sampling_rate=16000, return_tensors='pt')
            with torch.inference_mode():
                emissions = model(**{k: v.to(device) for k, v in inputs.items()}).logits.log_softmax(-1).cpu()
            targets = torch.tensor([target_ids], dtype=torch.int32)
            try:
                path, scores = AF.forced_align(emissions, targets, blank=0)
                spans = AF.merge_tokens(path[0], scores[0].exp(), blank=0)
                aligned = words_from_spans(words, normalized, spans, target_ids,
                                           len(audio) / rate / emissions.shape[1], offset, include_syllables)
            except (ValueError, RuntimeError):
                for word in words:
                    word['needs_review'] = True
                continue
            cursor = 0
            for segment in group:
                count = len(segment.get('words', []))
                if count:
                    segment['words'] = aligned[cursor:cursor + count]
                    segment['start'], segment['end'] = segment['words'][0]['start'], segment['words'][-1]['end']
                    cursor += count
        previous = None
        for segment in result:
            for word in segment.get('words', []):
                if previous and word['start'] < previous['end']:
                    previous['needs_review'] = word['needs_review'] = True
                previous = word
        return result
    finally:
        del model
        if device == 'cuda':
            torch.cuda.empty_cache()
