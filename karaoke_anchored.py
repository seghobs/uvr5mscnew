"""Keep acoustic locations instead of realigning an unanchored transcript globally."""
import copy
from karaoke_deep_words import deep_words, normalized


def bounded_refine(path, segments, language, refine):
    result=refine(path,copy.deepcopy(segments),language)
    if len(result)!=len(segments):raise ValueError('Hizalama satırları koruyamadı.')
    for original,updated in zip(segments,result):
        before,after=original['words'],updated.get('words',[])
        if len(before)!=len(after):raise ValueError('Hizalama kelimeleri koruyamadı.')
        for a,b in zip(before,after):
            b['needs_review']=bool(a.get('needs_review') or b.get('needs_review'))
        # Reject large relocation of an already acoustic word anchor.
        for i,(a,b) in enumerate(zip(before,after)):
            if abs(a['start']-b['start'])>.75 or abs(a['end']-b['end'])>.75:
                after[i]=copy.deepcopy(a);after[i]['needs_review']=True
        # A fallback must not create a new collision with a refined neighbour.
        for _ in range(len(after)):
            changed=False
            for i in range(1,len(after)):
                if after[i-1]['end']>after[i]['start']:
                    for j in (i-1,i):
                        if after[j]!=before[j]:changed=True
                        after[j]=copy.deepcopy(before[j]);after[j]['needs_review']=True
            if not changed:break
        if after:
            updated['start']=after[0]['start'];updated['end']=after[-1]['end']
    return result


def recognize_anchored(path,get_model,progress=lambda *args:None):
    import soundfile as sf
    from karaoke_ctc import refine_turkish
    duration=sf.info(path).duration
    rows=[]
    # Overlapping windows preserve context at each ownership boundary.
    for offset in range(0,int(duration)+1,40):
        if offset>=duration:break
        start=max(0,offset-5);end=min(duration,offset+45)
        result=deep_words(path,start,end,get_model,
            lambda p,m:progress(min(.98,(offset+p*40)/duration),m))
        candidates=result['candidates']
        if not candidates:continue
        words=combine_candidates(candidates)
        words=[w for w in words if offset<=(w['start']+w['end'])/2<min(duration,offset+40)]
        # Preserve each repeated occurrence; no text-based deduplication.
        for i in range(0,len(words),6):
            chunk=words[i:i+6]
            rows.append({'start':chunk[0]['start'],'end':chunk[-1]['end'],'text':' '.join(w['word'] for w in chunk),'words':chunk})
    if not rows:raise ValueError('Güvenli söz konumu bulunamadı; mevcut kayıt korundu.')
    return bounded_refine(path,rows,'tr',refine_turkish)


def combine_candidates(candidates):
    words=copy.deepcopy(candidates[0]['words']) if candidates else []
    for candidate in candidates[1:]:
        for word in candidate['words']:
            if word.get('probability',0)<.6:continue
            if all(word['end']<=w['start'] or word['start']>=w['end'] for w in words):
                words.append(copy.deepcopy(word))
    return sorted(words,key=lambda w:w['start'])


def anchor_exact_text(segment,candidates):
    original_tokens=segment['text'].split()
    tokens=[normalized(token) for token in original_tokens]
    if not tokens or not any(tokens):raise ValueError('Satır boş.')
    for candidate in candidates:
        words=candidate['words'];labels=[normalized(w['word']) for w in words]
        for i in range(len(words)-len(tokens)+1):
            if labels[i:i+len(tokens)]==tokens:
                selected=copy.deepcopy(words[i:i+len(tokens)])
                for word, token in zip(selected, original_tokens):
                    word['word']=token
                return {**segment,'start':selected[0]['start'],'end':selected[-1]['end'],'words':selected}
    raise ValueError('Düzeltilmiş sözler ses denemelerinde tam eşleşmedi; eski kayıt korundu.')


def anchor_transcript(text,recognized):
    remaining=[w for row in recognized for w in row['words']]
    rows=[]
    for line in text.splitlines():
        if not line.strip():continue
        row=anchor_exact_text({'text':line.strip()},[{'words':remaining}])
        rows.append(row)
        remaining=[w for w in remaining if w['start']>=row['end']]
    return rows
