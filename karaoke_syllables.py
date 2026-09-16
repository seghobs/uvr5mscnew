"""Propose Turkish syllable clips from acoustic character spans; never save lyrics."""
import math
import unicodedata


def syllable_ranges(text):
    vowels = [i for i, c in enumerate(text) if c in 'aeıioöuüâîû']
    if not vowels:
        return []
    # Keep the final consonant of an intervocalic cluster with the next vowel.
    cuts = [0] + [max(a+1, b-1) for a, b in zip(vowels, vowels[1:])] + [len(text)]
    return list(zip(cuts, cuts[1:]))


def detect_syllables(audio_path, segment):
    import soundfile as sf
    from karaoke_ctc import refine_turkish
    start, end = segment['start'], segment['end']
    info = sf.info(audio_path)
    if not all(math.isfinite(x) for x in (start, end)) or start < 0 or end <= start or end > info.duration or end-start > 20:
        raise ValueError('Hece tespiti için ses içinde en fazla 20 saniyelik bir satır seçin.')
    tokens = segment['text'].split()
    if not tokens or len(segment['text']) > 400:
        raise ValueError('Satır boş veya çok uzun.')
    import numpy as np
    samples, _ = sf.read(audio_path, start=int(start*info.samplerate), stop=int(end*info.samplerate), dtype='float32')
    if not samples.size or not np.isfinite(samples).all():
        raise ValueError('Seçilen ses bölümü okunamadı.')
    if float(np.max(np.abs(samples))) < 1e-5:
        return {'passages': [], 'skipped': tokens, 'message': 'Bu bölümde duyulabilir ses bulunamadı; hece üretilmedi.'}
    # Use the corrected transcript, not stale word labels or guessed equal times.
    # Standalone punctuation has no acoustic target. Preserve original indexes
    # so removing it from the model input never shifts subsequent word links.
    spoken = [(i,t) for i,t in enumerate(tokens) if any(not unicodedata.category(c).startswith('P') for c in t)]
    if not spoken:
        return {'passages': [], 'skipped': [], 'word_times': [], 'message': 'Bu satır yalnızca noktalama içeriyor.'}
    source = {'start': start, 'end': end, 'text': ' '.join(t for _,t in spoken),
              'words': [{'word': t, 'start': start, 'end': end} for _,t in spoken]}
    aligned = refine_turkish(audio_path, [source], 'tr', include_syllables=True, context_padding=0)
    aligned[0]['words'] = recover_weak_words(audio_path, aligned[0]['words'], start, end, refine_turkish)
    passages, skipped, word_times = [], [], []
    for position, word in enumerate(aligned[0]['words']):
        wi = spoken[position][0]
        # Word boundaries remain useful when a short internal syllable is rejected.
        a, b, score = word['start'], word['end'], word.get('probability', 0) or 0
        if (word.get('timing_source') == 'ctc' and all(math.isfinite(x) for x in (a,b,score))
                and start <= a < b <= end and score >= .15):
            word_times.append({'index': wi, 'start': a, 'end': b, 'score': score})
        syllables = word.get('syllables', [])
        if not syllables:
            skipped.append(word['word'])
        for si, syllable in enumerate(syllables):
            a, b, score = syllable['start'], syllable['end'], syllable['score']
            if not all(math.isfinite(x) for x in (a,b,score)) or a < start or b > end or b-a < .025 or score < .15:
                skipped.append(syllable['text'])
                continue
            passages.append({'id': f'auto:{wi}:{si}:{a:.8f}:{b:.8f}', 'start': a, 'end': b,
                             'label': syllable['text'].replace('i','İ').replace('ı','I').upper(),
                             'needs_review': True, 'score': score})
    return {'passages': passages, 'skipped': skipped, 'word_times': word_times,
            'message': f'{len(passages)} hece önerisi bulundu. Dinleyip doğrulayın; mevcut bağlantılar korundu.'}


def recover_weak_words(audio_path, words, start, end, align):
    """Retry weak runs only in gaps between strong words, without moving anchors."""
    import copy
    result=copy.deepcopy(words)
    def reliable(w):
        return w.get('timing_source')=='ctc' and (w.get('probability') or 0)>=.5 and start<=w['start']<w['end']<=end
    anchors=[i for i,w in enumerate(words) if reliable(w)]
    if not anchors:return result
    retries=0
    for left,right in zip([-1]+anchors,anchors+[len(words)]):
        if right-left<=1 or retries>=4:continue
        a=words[left]['end'] if left>=0 else start
        b=words[right]['start'] if right<len(words) else end
        if b-a<.08 or b-a>20:continue
        original=words[left+1:right]
        target={'start':a,'end':b,'text':' '.join(w['word'] for w in original),
                'words':[{'word':w['word'],'start':a,'end':b} for w in original]}
        retries+=1
        try:
            retried=align(audio_path,[target],'tr',include_syllables=True,context_padding=0)[0]['words']
        except (ValueError,RuntimeError):continue
        if len(retried)!=len(original):continue
        previous=a
        for index,(old,new) in enumerate(zip(original,retried),left+1):
            s,e,score=new['start'],new['end'],new.get('probability') or 0
            if new['word']!=old['word'] or new.get('timing_source')!='ctc':continue
            if not all(math.isfinite(x) for x in (s,e,score)) or not previous<=s<e<=b or e-s<.04 or score<.15:continue
            # A moderate retry is useful only when it improves an already located
            # acoustic occurrence. New/unlocated guesses still require a strong score.
            if score<.5 and (old.get('timing_source')!='ctc' or old['end']<=old['start']
                             or score<=float(old.get('probability') or 0)):continue
            if any(w.get('timing_source')=='ctc' and w['end']>w['start'] and
                   (w['end']>s if j<index else w['start']<e)
                   for j,w in enumerate(result) if j!=index):continue
            # A retry must agree with an existing weak acoustic occurrence.
            if old.get('timing_source')=='ctc' and old['end']>old['start']:
                overlap=max(0,min(e,old['end'])-max(s,old['start']))
                if overlap<.5*min(e-s,old['end']-old['start']):continue
            result[index]={**old,**new,'needs_review':True}
            previous=e
    return result
