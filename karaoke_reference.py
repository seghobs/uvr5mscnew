"""Read-only reference lookup and conservative, recording-order lyric comparison."""
import copy
import json
import re
from difflib import SequenceMatcher
from functools import lru_cache
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen

CLIENT = 'UVR5-Karaoke/1.0 (https://github.com/seghobs/uvr5mscnew)'


def _get_json(url):
    # Only callers below construct URLs; user input cannot choose the host.
    with urlopen(Request(url, headers={'User-Agent': CLIENT}), timeout=15) as response:
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError('Söz kaynağının yanıtı çok büyük.')
        return json.loads(data)


def youtube_id(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be'):
        raise ValueError('Geçerli bir HTTPS YouTube video bağlantısı girin.')
    ident = parsed.path.strip('/') if parsed.hostname == 'youtu.be' else parse_qs(parsed.query).get('v', [''])[0]
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', ident):
        raise ValueError('YouTube video kimliği bulunamadı.')
    return ident


def normalize(text):
    return re.sub(r'[^\w]', '', text.replace('İ', 'i').replace('I', 'ı').lower(), flags=re.UNICODE)


@lru_cache(maxsize=32)
def search_reference(url='', artist='', title=''):
    if url and not (artist.strip() and title.strip()):
        ident = youtube_id(url)
        meta = _get_json('https://www.youtube.com/oembed?' + urlencode({'url': 'https://www.youtube.com/watch?v=' + ident, 'format': 'json'}))
        clean = re.sub(r'\s*[|].*$', '', meta['title'])
        clean = re.sub(r'\s*[\[(](?:official|resmi|lyrics?|visualizer|music video).*?[\])]', '', clean, flags=re.I).strip()
        parts = re.split(r'\s+[-–—]\s+', clean, maxsplit=1)
        artist = artist or (parts[0] if len(parts) == 2 else meta.get('author_name', '').replace(' - Topic', ''))
        title = title or parts[-1]
    if not artist.strip() or not title.strip():
        raise ValueError('Sanatçı ve şarkı adını girin veya YouTube bağlantısını kullanın.')
    records = _get_json('https://lrclib.net/api/search?' + urlencode({'artist_name': artist.strip(), 'track_name': title.strip()}))
    candidates = []
    for record in records[:20]:
        text = record.get('plainLyrics') or re.sub(r'\[[^\]]+\]', '', record.get('syncedLyrics') or '')
        if not text.strip() or record.get('instrumental'):
            continue
        candidates.append({'id': record['id'], 'artist': record.get('artistName', ''), 'title': record.get('trackName', ''),
                           'album': record.get('albumName', ''), 'duration': record.get('duration'), 'text': text.strip(),
                           'source': 'LRCLIB (topluluk kaynağı)', 'url': f"https://lrclib.net/api/get/{record['id']}"})
    return {'artist': artist, 'title': title, 'candidates': candidates}


def compare_reference(segments, reference):
    """Match each recorded row to a reference window, preserving repeated choruses.

    Never add missing verses or delete unmatched audio. Similarity is lexical,
    not acoustic confidence; every changed row is reviewable before alignment.
    """
    tokens = reference.split()
    keys = [normalize(t) for t in tokens]
    if not tokens or len(tokens) > 5000:
        raise ValueError('Referans metin 1–5000 kelime içermeli.')
    rows = []
    for index, seg in enumerate(segments):
        original = seg['text'].split()
        old = [normalize(t) for t in original]
        best = (0.0, '')
        # A row can span reference line breaks, including a split/merged word.
        for length in range(max(1, len(old) - 2), min(len(keys), len(old) + 2) + 1):
            for start in range(len(keys) - length + 1):
                window = keys[start:start + length]
                score = SequenceMatcher(None, ' '.join(old), ' '.join(window), autojunk=False).ratio()
                if score > best[0]:
                    best = score, ' '.join(tokens[start:start + length])
        matched = best[0] >= .72
        proposed = best[1] if matched else seg['text']
        changed = [normalize(t) for t in proposed.split()] != old
        rows.append({'index': index, 'original': seg['text'], 'proposed': proposed,
                     'similarity': round(best[0], 3), 'changed': changed,
                     'reason': 'Fark bulundu; kayıttan kontrol edin.' if changed else
                               ('Metin eşleşiyor.' if matched else 'Güvenilir metin eşleşmesi yok; mevcut satır korundu.')})
    return rows


def align_changed_rows(audio_path, segments, edits, align):
    """Crop inside neighbouring word boundaries; commit only a complete valid result."""
    import soundfile as sf
    import tempfile
    from pathlib import Path
    from karaoke_timing import timing_issues
    result = copy.deepcopy(segments)
    info = sf.info(str(audio_path))
    duration = info.frames / info.samplerate
    for index, text in sorted(edits.items()):
        if index < 0 or index >= len(segments) or not text.strip():
            raise ValueError('Düzeltilecek satır veya metin geçersiz.')
        seg = segments[index]
        left = segments[index - 1]['end'] if index else 0
        right = segments[index + 1]['start'] if index + 1 < len(segments) else duration
        # Adjacent edited rows use their shared original midpoint, never overlapping.
        start = max(left, seg['start'] - .35)
        end = min(right, seg['end'] + .35, duration)
        if index - 1 in edits:
            start = max(start, (segments[index - 1]['end'] + seg['start']) / 2)
        if index + 1 in edits:
            end = min(end, (seg['end'] + segments[index + 1]['start']) / 2)
        first, last = round(start * info.samplerate), round(end * info.samplerate)
        if first < 0 or last <= first:
            raise ValueError(f'Satır {index + 1}: güvenli ses aralığı bulunamadı.')
        start = first / info.samplerate
        samples, rate = sf.read(str(audio_path), start=first, stop=last)
        with tempfile.TemporaryDirectory(prefix='karaoke-reference-') as folder:
            clip = Path(folder) / 'vocal.wav'
            sf.write(str(clip), samples, rate, subtype='FLOAT')
            aligned = align(clip, text)
        words = [w for s in aligned for w in s.get('words', [])]
        if [normalize(w['word']) for w in words] != [normalize(t) for t in text.split()]:
            raise ValueError(f'Satır {index + 1}: düzeltmenin tüm kelimeleri hizalanamadı.')
        for word in words:
            word['start'] += start
            word['end'] += start
        result[index] = {'start': words[0]['start'], 'end': words[-1]['end'], 'text': ' '.join(w['word'] for w in words), 'words': words}
        if words[0]['start'] < start - 1e-7 or words[-1]['end'] > last / rate + 1e-7:
            raise ValueError(f'Satır {index + 1}: hizalama ses aralığını aştı.')
    errors = timing_issues(result, include_review=False)
    if errors:
        raise ValueError('; '.join(errors[:3]))
    return result
