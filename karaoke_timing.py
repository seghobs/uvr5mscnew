"""Lossless karaoke timing contract. No duration redistribution or guessed words."""
import math
import copy
import re
from decimal import Decimal, ROUND_CEILING


def repair_timing(segments):
    """Repair sub-sample overflow only; never guess acoustic word boundaries."""
    result = copy.deepcopy(segments)
    previous = None
    for seg in result:
        for word in seg.get('words') or []:
            start, end = word.get('start'), word.get('end')
            if not all(isinstance(t, (int, float)) and math.isfinite(t) for t in (start, end)) or start < 0 or end <= start:
                previous = None
                continue
            if previous and 0 < previous['end'] - start <= 1 / 16000:
                if previous['start'] < start:
                    previous['end'] = start
            previous = word
    for seg in result:
        words = seg.get('words') or []
        if words and all(isinstance(w.get(k), (int, float)) and math.isfinite(w[k]) for w in words for k in ('start','end')) and all(w['start'] >= 0 and w['end'] > w['start'] for w in words):
            # Expand an obsolete envelope, retaining intentional lead-in/out.
            if isinstance(seg.get('start'), (int, float)) and math.isfinite(seg['start']):
                seg['start'] = min(seg['start'], min(w['start'] for w in words))
            if isinstance(seg.get('end'), (int, float)) and math.isfinite(seg['end']):
                seg['end'] = max(seg['end'], max(w['end'] for w in words))
    return result


def timing_issues(segments, require_words=True, include_review=True):
    issues = []
    previous_end = 0.0
    for i, seg in enumerate(segments):
        label = f"Satır {i + 1}"
        start, end = seg.get("start"), seg.get("end")
        if not all(isinstance(t, (int, float)) and math.isfinite(t) for t in (start, end)) or start < 0 or end <= start:
            issues.append(f"{label}: geçersiz satır süresi")
            continue
        words = seg.get("words") or []
        if not words:
            if require_words:
                issues.append(f"{label}: kelimeler sesle hizalanmalı")
            continue
        if " ".join(w["word"].strip() for w in words) != " ".join(seg.get("text", "").split()):
            issues.append(f"{label}: metin değişmiş, yeniden hizalama gerekli")
        for j, word in enumerate(words):
            ws, we = word.get("start"), word.get("end")
            name = f"{label}, kelime {j + 1}"
            if not all(isinstance(t, (int, float)) and math.isfinite(t) for t in (ws, we)) or ws < 0 or we <= ws:
                issues.append(f"{name}: geçersiz kelime süresi")
                continue
            if ws < previous_end - 1e-7:
                issues.append(f"{name}: önceki kelimeyle çakışıyor")
            if ws < start - 1e-7 or we > end + 1e-7:
                issues.append(f"{name}: satır aralığının dışında")
            if (include_review and word.get("needs_review")) or word.get("timing_source") == "estimated":
                issues.append(f"{name}: zamanlama doğrulanmalı")
            previous_end = max(previous_end, we)
    return issues


def centiseconds(seconds):
    # Ceiling means a fill can never start BEFORE its canonical timestamp.
    return int((Decimal(str(seconds)) * 100).to_integral_value(rounding=ROUND_CEILING))


def ass_time(seconds):
    cs = centiseconds(seconds)
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def escape_ass(text):
    return str(text).replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", " ").replace("\r", " ")


def ass_word_tags(segment):
    errors = timing_issues([segment], include_review=False)
    if errors:
        raise ValueError("; ".join(errors[:4]))
    cursor = centiseconds(segment["start"])
    tags = []
    for i, word in enumerate(segment["words"]):
        start, end = centiseconds(word["start"]), centiseconds(word["end"])
        # Explicit empty karaoke syllables preserve initial and inter-word silence.
        if start > cursor:
            tags.append(f"{{\\k{start - cursor}}}\\h")
        tags.append(f"{{\\kf{end - start}}}{escape_ass(word['word'].strip())}")
        if i < len(segment["words"]) - 1:
            tags.append(" ")
        cursor = end
    return "".join(tags)


def align_lyrics(model, audio_path, text, language):
    """Align the ENTIRE supplied transcript against audio using the existing model."""
    from stable_whisper.alignment import align
    result = align(
        model, str(audio_path), text, language=language,
        original_split=True, regroup=False, fast_mode=False,
        remove_instant_words=False, max_word_dur=None,
        suppress_silence=True, suppress_word_ts=True, vad=False,
        verbose=None,
    )
    if result is None:
        raise ValueError("Ses ile metin eşleştirilemedi; mevcut kayıt korundu.")
    segments = []
    for seg in result.to_dict()["segments"]:
        words = []
        for w in seg.get("words", []):
            if not w["word"].strip():
                continue
            words.append({
                "word": w["word"].strip(), "start": w["start"], "end": w["end"],
                "probability": w.get("probability"), "timing_source": "aligned",
                "needs_review": w["end"] <= w["start"] or (w.get("probability") is not None and w["probability"] < 0.35),
            })
        if words:
            segments.append({"start": words[0]["start"], "end": words[-1]["end"],
                             "text": " ".join(w["word"] for w in words), "words": words})
    # Never silently omit part of a pasted transcript.
    compact = lambda s: re.sub(r"\s+", "", s)
    if compact("".join(s["text"] for s in segments)) != compact(text):
        raise ValueError("Hizalama tüm sözleri koruyamadı; mevcut kayıt değiştirilmedi.")
    if not segments:
        raise ValueError("Hizalanmış kelime bulunamadı.")
    return segments
