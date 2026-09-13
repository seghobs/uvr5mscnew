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
            lambda p,m:progress(min(.98,(offset+p*40)/duration),m),strict=True)
        candidates=result['candidates']
        if not candidates:continue
        words=verified_candidates(candidates)
        words=[w for w in words if offset<=(w['start']+w['end'])/2<min(duration,offset+40)]
        # Preserve each repeated occurrence; no text-based deduplication.
        for chunk in word_groups(words):
            rows.append({'start':chunk[0]['start'],'end':chunk[-1]['end'],'text':' '.join(w['word'] for w in chunk),'words':chunk})
    if not rows:raise ValueError('Güvenli söz konumu bulunamadı; mevcut kayıt korundu.')
    return bounded_refine(path,rows,'tr',refine_turkish)


def word_groups(words):
    chunk=[]
    for word in words:
        if chunk and (len(chunk)>=6 or word['start']-chunk[-1]['end']>=3):
            yield chunk
            chunk=[]
        chunk.append(word)
    if chunk:yield chunk


def verified_candidates(candidates):
    """Require four distinct passes, matching both text and acoustic occurrence."""
    by_run={c.get('run_id'):c for c in candidates if c.get('run_id') in range(4)}
    if set(by_run)!={0,1,2,3}:return []
    result=[]
    used={run:set() for run in range(1,4)}
    for word in by_run[0]['words']:
        label=normalized(word['word'])
        if not label or word.get('probability',0)<.6:continue
        matches=[]
        for run in range(1,4):
            choices=[(i,w) for i,w in enumerate(by_run[run]['words'])
                     if i not in used[run] and normalized(w['word'])==label
                     and w.get('probability',0)>=.6
                     and min(w['end'],word['end'])>max(w['start'],word['start'])
                     and abs(w['start']-word['start'])<=.75
                     and abs(w['end']-word['end'])<=.75]
            if not choices:break
            matches.append(min(choices,key=lambda pair:abs(pair[1]['start']-word['start'])))
        if len(matches)!=3:continue
        if result and word['start']<result[-1]['end']:continue
        for run,(index,_) in enumerate(matches,1):used[run].add(index)
        result.append(copy.deepcopy(word))
    return result


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


def anchor_transcript_rows(text,recognized,progress=lambda *args:None):
    """Try every pasted line in recording order; retain unaligned text explicitly."""
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    remaining=sorted([copy.deepcopy(w) for row in recognized for w in row.get('words',[])],key=lambda w:w['start'])
    rows=[];cursor=0.;pending=[]
    for index,line in enumerate(lines):
        progress((index+1)/max(1,len(lines)),f'Satır satır senkron: {index+1}/{len(lines)}')
        try:
            row=anchor_exact_text({'text':line},[{'words':remaining}])
            cursor=row['end']
            remaining=[w for w in remaining if w['start']>=cursor]
        except ValueError:
            # Zero duration is an explicit unsynchronized state, never invented time.
            row={'text':line,'start':cursor,'end':cursor,'words':[]}
            pending.append(index+1)
        rows.append(row)
    return rows,{'mode':'line_by_line','total':len(lines),'aligned':len(lines)-len(pending),'pending':pending}
