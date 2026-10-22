"""Turkish character alignment after coarse Whisper alignment.

Model: mpoyraz/wav2vec2-xls-r-300m-cv7-turkish (CC BY 4.0).
No duration splitting or repeated-word deduplication is performed.
"""
import copy
import math
from numbers import Real
import unicodedata
from pathlib import Path

MODEL_ID = 'mpoyraz/wav2vec2-xls-r-300m-cv7-turkish'
MODEL_REVISION = '708639f50559d7970f462e13ec64d3f059ca89f6'
MODEL_DIR = Path(__file__).resolve().parent / 'models/alignment/turkish-ctc'


def acoustic_probability(word):
    """Unscored placeholders are not acoustic evidence or a fatal error."""
    value = word.get('probability')
    return float(value) if isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 1 else 0.

# Copy/paste can mix scripts that render identically. This is visual repair,
# not transliteration: require Latin context (or a single lookalike letter).
LOOKALIKE_LETTERS = str.maketrans({
    'А':'A','В':'B','С':'C','Е':'E','Н':'H','І':'I','Ј':'J','К':'K',
    'М':'M','О':'O','Р':'P','Ѕ':'S','Т':'T','Х':'X','У':'Y',
    'а':'a','с':'c','е':'e','і':'i','ј':'j','о':'o','р':'p','ѕ':'s','х':'x','у':'y',
    'Α':'A','Β':'B','Ε':'E','Ζ':'Z','Η':'H','Ι':'I','Κ':'K','Μ':'M',
    'Ν':'N','Ο':'O','Ρ':'P','Τ':'T','Υ':'Y','Χ':'X','ο':'o',
})


def acoustic_text(text, vocab):
    text = unicodedata.normalize('NFKC', text)
    letters = [c for c in text if c.isalpha()]
    if len(letters)==1 or any('LATIN' in unicodedata.name(c,'') for c in letters):
        text = text.translate(LOOKALIKE_LETTERS)
    text = (text.replace('I','i').replace('İ','i') if getattr(vocab,'language','tr') == 'kmr'
            else text.replace('I','ı').replace('İ','i')).lower()
    result=[]
    for char in text:
        category=unicodedata.category(char)
        if category.startswith('P') or category=='Cf' or '\ufe00'<=char<='\ufe0f':continue
        if char not in vocab and 'LATIN' in unicodedata.name(char,''):
            # Preserve Turkish letters present in the model; fold only other
            # Latin accents such as circumflexes and imported acute accents.
            char=''.join(c for c in unicodedata.normalize('NFD',char) if unicodedata.category(c)!='Mn')
        result.append(char)
    return ''.join(result)


def alignment_mono(audio, channel):
    if channel not in ('mix', 'left', 'right'):
        raise ValueError('Geçersiz ses kanalı')
    if audio.ndim != 2:
        return audio
    return audio.mean(axis=1) if channel == 'mix' else audio[:, 0 if channel == 'left' else min(1, audio.shape[1]-1)]


def clamp_sample_start(aligned, start, rate):
    # Fix less than one sample of rounding, without importing outside audio.
    for word in aligned:
        for item in [word, *word.get('syllables', [])]:
            if start - 1/rate <= item['start'] < start:
                item['start'] = start


def normalized_words(words, vocab):
    result = []
    for word in words:
        text = acoustic_text(word['word'], vocab)
        if not text or any(c not in vocab or c.isspace() for c in text):
            raise ValueError('Kelimenin tüm harfleri hizalama modelinde temsil edilemiyor.')
        result.append(text)
    return result


def supported_targets(words, vocab):
    """Keep a one-to-one index map; never truncate an unsupported word."""
    indices=[];normalized=[]
    for index,word in enumerate(words):
        try:target=normalized_words([word],vocab)[0]
        except ValueError:continue
        indices.append(index);normalized.append(target)
    return indices,normalized


def restore_unsupported_words(words, indices, aligned, start):
    """An unrepresentable word stays visible and unbound, not falsely timed."""
    known=dict(zip(indices,aligned));result=[];previous=start
    for index,word in enumerate(words):
        if index in known:
            result.append(known[index]);previous=known[index]['end']
        else:
            result.append({**word,'start':previous,'end':previous,'probability':0.,
                           'timing_source':'estimated','needs_review':True})
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


def normalize_fading_audio(audio, rate):
    """Bounded local gain for analysis only; never change the saved soundtrack."""
    import numpy as np
    from scipy.ndimage import uniform_filter1d
    power=uniform_filter1d(np.asarray(audio,dtype='float32')**2,max(1,round(rate*.30)))
    gain=np.minimum(50.,.08/np.maximum(np.sqrt(np.maximum(power,0)),.00001))
    return audio*gain


def refine_turkish(audio_path, segments, language, progress=None, include_syllables=False, context_padding=.8, channel='mix', normalize_fade=False,session=None):
    if channel not in ('mix','left','right'):raise ValueError('Geçersiz ses kanalı')
    if language != 'tr': return segments
    return refine_ctc(audio_path,segments,language,progress,include_syllables,context_padding,channel,normalize_fade,session=session)


def refine_ctc(audio_path, segments, language, progress=None, include_syllables=False, context_padding=.8, channel='mix', normalize_fade=False,independent_rows=False,session=None):
    if channel not in ('mix', 'left', 'right'):
        raise ValueError('Geçersiz ses kanalı')
    import soundfile as sf
    import torch
    import torchaudio.functional as AF
    from transformers import Wav2Vec2ForCTC, Wav2Vec2FeatureExtractor

    from karaoke_inference import RefinementSession
    owns_session=session is None
    if session is None:session=RefinementSession()
    inference_cache,vocab=session.load(language,progress)
    result = copy.deepcopy(segments)
    info = sf.info(audio_path)
    # Align neighbouring lines together, so the same sound cannot be assigned
    # independently to the last word of one line and the first of the next.
    groups = []
    for segment in result:
        if not groups or independent_rows or segment['end'] - groups[-1][0]['start'] > 18:
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
            start = max(0, group[0]['start'] - context_padding)
            end = min(info.duration, group[-1]['end'] + context_padding)
            if index:
                start = max(start, boundaries[index - 1])
            if index < len(groups) - 1:
                end = min(end, boundaries[index])
            # A bad coarse segment must not trigger unbounded GPU allocation.
            if end <= start or end - start > 22:
                for word in words:
                    word['needs_review'] = True
                continue
            indices,normalized = supported_targets(words, vocab)
            target_ids = [vocab[c] for c in '|'.join(normalized)]
            if not target_ids:
                for word in words:
                    word['needs_review'] = True
                continue
            first_sample = int(start * info.samplerate)
            offset = first_sample / info.samplerate
            audio, rate = sf.read(audio_path, start=first_sample, stop=int(end * info.samplerate), dtype='float32')
            audio = alignment_mono(audio, channel)
            if normalize_fade:audio=normalize_fading_audio(audio,rate)
            emissions=inference_cache.infer(audio,rate)
            if emissions is None:
                for word in words:word['needs_review']=True
                continue
            targets = torch.tensor([target_ids], dtype=torch.int32)
            try:
                path, scores = AF.forced_align(emissions, targets, blank=vocab['[PAD]'])
                spans = AF.merge_tokens(path[0], scores[0].exp(), blank=vocab['[PAD]'])
                aligned = words_from_spans([words[i] for i in indices], normalized, spans, target_ids,
                                           len(audio) / rate / emissions.shape[1], offset, include_syllables)
                aligned = restore_unsupported_words(words, indices, aligned, start)
                # Reading starts at floor(start * rate). Clamp only the sub-sample
                # rounding residue, never a genuinely out-of-range occurrence.
                clamp_sample_start(aligned, start, rate)
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
        inference_cache=None
        if owns_session:session.close()
