"""Align user-supplied Turkish lyrics; never transcribe or replace their text."""
import copy
import math
import re
import unicodedata


def instrumental(row):
    return bool(re.fullmatch(r'\s*(solo|enstr[üu]mantal|instrumental)[.\s…!]*',row['text'],re.I))


def spoken(token):
    return any(not unicodedata.category(c).startswith('P') for c in token)


def alignment_mono(audio):
    """Preserve a stereo vocal when opposite phases cancel the mono mix."""
    import numpy as np
    if audio.ndim!=2:return audio
    mix=audio.mean(axis=1);powers=np.mean(audio**2,axis=0)
    if np.mean(mix**2)<.05*max(float(powers.max()),1e-12):
        return audio[:,int(np.argmax(powers))]
    return mix


def protected(row):
    words=row.get('words') or []
    return row.get('locked') or (not instrumental(row) and len(words)==len(row['text'].split()) and
        all(w['word']==t and w.get('timing_source')=='manual' and not w.get('needs_review',False) and
            w['end']>w['start'] for w,t in zip(words,row['text'].split())))


def alignment_blocks(rows,duration):
    """Confirmed manual rows delimit search; unconfirmed coarse times are ignored."""
    blocks=[];indices=[];start=0.
    for i,row in enumerate(rows):
        if protected(row):
            if not (math.isfinite(row['start']) and math.isfinite(row['end']) and
                    start<=row['start']<row['end']<=duration):
                raise ValueError(f'Satır {i+1}: korunan süreler sıralı ve sesin içinde olmalı.')
            if indices:blocks.append((indices,start,row['start']))
            indices=[];start=row['end']
        elif not instrumental(row) and row['text'].strip():indices.append(i)
    if indices:blocks.append((indices,start,duration))
    return blocks


def trim_unvoiced_repeat_prefixes(rows):
    """Drop only generated duplicate prefixes with no independent acoustic span."""
    count=0
    for previous,row in zip(rows,rows[1:]):
        if protected(row) or not str(row.get('id','')).startswith('auto-repeat:'):continue
        words=row.get('words') or []
        before=previous.get('words') or []
        if not words or not before:continue
        prefix=words[0];last=before[-1]
        if (prefix['word'].strip().casefold()==last['word'].strip().casefold()
                and prefix['end']<=prefix['start'] and last['end']>last['start']
                and last['start']-.05<=prefix['start']<=last['end']+.05):
            row['words']=words[1:];row['text']=' '.join(w['word'] for w in words[1:]);count+=1
    return count


def assemble(rows,aligned_blocks,duration):
    result=copy.deepcopy(rows);pending=[];linked=0;total=0
    for indices,words in aligned_blocks:
        cursor=0
        for index in indices:
            row=result[index];tokens=row['text'].split();updated=[]
            for token_index,token in enumerate(tokens):
                if not spoken(token):
                    updated.append({'word':token,'start':row['start'],'end':row['start'],
                                    'timing_source':'estimated','needs_review':False});continue
                if cursor>=len(words) or words[cursor]['word']!=token:
                    raise ValueError('Verilen sözlerin sırası korunamadı; mevcut kayıt değiştirilmedi.')
                word=words[cursor];cursor+=1;total+=1
                original=(row.get('words') or [])
                manual=original[token_index] if token_index<len(original) else None
                if manual and manual['word']==token and manual.get('timing_source')=='manual' and \
                   not manual.get('needs_review',False) and manual['end']>manual['start']:
                    updated.append(copy.deepcopy(manual));linked+=1;continue
                # A forced path alone is not proof that an absent word was sung.
                if word['probability']<.10 or word['end']<=word['start']:
                    word={'word':token,'start':row['start'],'end':row['start'],
                          'timing_source':'estimated','needs_review':True}
                else:linked+=1
                updated.append(word)
            row['words']=updated
            good=[w for w in updated if w['end']>w['start']]
            if good:row['start']=good[0]['start'];row['end']=good[-1]['end']
            if any(w.get('needs_review') for w in updated):pending.append(index+1)
        if cursor!=len(words):raise ValueError('Fazladan söz çıktısı reddedildi.')
    # Interlude labels consume no acoustic targets; they fill the genuine gap.
    for i,row in enumerate(result):
        if not instrumental(row) or row.get('locked'):continue
        before=result[i-1]['end'] if i else 0.
        after=result[i+1]['start'] if i+1<len(result) else duration
        if after>before:
            row.update(start=before,end=after,words=[{'word':row['text'].strip(),'start':before,'end':after,
                'timing_source':'manual','needs_review':False}])
    trimmed=trim_unvoiced_repeat_prefixes(result)
    pending=[i+1 for i,row in enumerate(result) if any(w.get('needs_review') for w in row.get('words') or [])]
    previous=0.
    for row in result:
        for word in row.get('words') or []:
            if word['end']<=word['start']:continue
            if not (math.isfinite(word['start']) and math.isfinite(word['end']) and
                    previous<=word['start']<word['end']<=duration):
                raise ValueError('Korunan elle bağlı kelimelerle çakışma bulundu; mevcut sözler değiştirilmedi.')
            previous=word['end']
    return result,{'method':'supplied_turkish_ctc','linked_words':linked,'target_words':total,
                   'review_rows':pending,'trimmed_repeat_prefixes':trimmed,'preserved_rows':sum(bool(protected(r)) for r in rows)}


def align_supplied(audio_path,rows,progress=lambda *args:None,instrumental_path=None,diagnostics=None):
    import soundfile as sf
    import torch
    import torchaudio.functional as AF
    from transformers import Wav2Vec2ForCTC,Wav2Vec2FeatureExtractor
    from karaoke_ctc import MODEL_DIR,MODEL_ID,MODEL_REVISION,normalized_words,words_from_spans
    from karaoke_interludes import generated,music_evidence,place_interludes,regions
    from karaoke_repeat_spotting import expand_supplied_rows,local_verifier
    import json
    rows=[copy.deepcopy(r) for r in rows if not generated(r)]
    original_rows=rows
    info=sf.info(str(audio_path));duration=info.frames/info.samplerate
    blocks=alignment_blocks(rows,duration)
    music_regions,voice_regions,available=music_evidence(audio_path,instrumental_path)
    repeat_report={'repeated_rows_added':0,'repeat_candidates':0,
                   'repeat_method':'supplied_text_ctc_occurrence_graph','repeat_accuracy_guaranteed':False,'repeat_review_candidates':[],'repaired_word_spans':0,'terminal_repeats_added':0}
    last_progress=0.
    def emit(value,message):
        nonlocal last_progress
        last_progress=max(last_progress,min(.99,value));progress(last_progress,message)
    def finish(completed):
        result,report=assemble(rows,completed,duration)
        report.update(repeat_report)
        result,solo_report=place_interludes(result,duration,voice_regions,music_regions,available)
        for row in result:row['alignment_mode']='supplied_ctc'
        report.update(solo_report)
        report['review_rows']=[i+1 for i,r in enumerate(result) if not instrumental(r) and
                               any(w.get('needs_review') for w in r.get('words') or [])]
        if diagnostics is not None:
            diagnostics.update(raw_blocks=copy.deepcopy(completed),voice_regions=voice_regions,music_regions=music_regions)
        return result,report
    if not blocks:return finish([])
    if not (MODEL_DIR/'pytorch_model.bin').is_file():
        from huggingface_hub import snapshot_download
        emit(0,'Türkçe hizalama modeli indiriliyor…')
        snapshot_download(MODEL_ID,revision=MODEL_REVISION,local_dir=str(MODEL_DIR),
            allow_patterns=['config.json','preprocessor_config.json','vocab.json','pytorch_model.bin'])
    vocab=json.loads((MODEL_DIR/'vocab.json').read_text(encoding='utf8'))
    device='cuda' if torch.cuda.is_available() and torch.cuda.mem_get_info()[0]>3*1024**3 else 'cpu'
    model=Wav2Vec2ForCTC.from_pretrained(MODEL_DIR,local_files_only=True).eval().to(device)
    extractor=Wav2Vec2FeatureExtractor.from_pretrained(MODEL_DIR,local_files_only=True)
    hop=math.prod(model.config.conv_stride)
    if hop!=320:raise ValueError('Türkçe modelin zaman çözünürlüğü değişmiş.')
    before={};after={};replacements={};local_completed=[]
    try:
        for block_index,(indices,start,end) in enumerate(blocks):
            audio,rate=sf.read(str(audio_path),start=round(start*info.samplerate),stop=round(end*info.samplerate),
                               dtype='float32',always_2d=True)
            views=[alignment_mono(audio)]
            if audio.shape[1]>1 and float(((audio[:,0]-audio[:,-1])**2).mean())>1e-10:
                views.append(audio[:,-1])
            emissions=[];core=16*16000;context=16000
            for view_index,view in enumerate(views):
                wave=AF.resample(torch.from_numpy(view.copy()),rate,16000)
                chunks=[]
                for offset in range(0,len(wave),core):
                    left=max(0,offset-context);right=min(len(wave),offset+core+context)
                    emit(.96*(block_index+.68*(view_index+offset/max(1,len(wave)))/len(views))/len(blocks),
                         f'Ses kanalı {view_index+1}/{len(views)} kontrol ediliyor · {start+offset/16000:.0f}/{duration:.0f} sn')
                    clip=wave[left:right]
                    if len(clip)<400:break
                    inputs=extractor(clip.numpy(),sampling_rate=16000,return_tensors='pt')
                    with torch.inference_mode():
                        logits=model(**{k:v.to(device) for k,v in inputs.items()}).logits.log_softmax(-1).cpu()
                    first=(offset-left)//hop
                    last=first+core//hop if offset+core<len(wave) else logits.shape[1]
                    chunks.append(logits[:,first:last])
                if not chunks:raise ValueError('Ses hizalama için çok kısa.')
                emissions.append(torch.cat(chunks,dim=1).contiguous())
            local_rows=[{**rows[i],'_original_index':i} for i in indices]
            verifier=local_verifier(audio,rate,model,extractor,vocab,device,
                       lambda p,message:emit(.96*(block_index+.85)/len(blocks),message))
            verified_cache={}
            def verify(row,a,b):
                key=(row['text'],round(a,2),round(b,2))
                if key not in verified_cache:verified_cache[key]=verifier(row,a,b)
                return verified_cache[key]
            expanded,report,hits=expand_supplied_rows(local_rows,[e[0].numpy() for e in emissions],vocab,
                lambda p,message:emit(.96*(block_index+.68+.17*p)/len(blocks),message),rescue=verify)
            repeat_report['repeated_rows_added']+=report['repeated_rows_added']
            repeat_report['terminal_repeats_added']+=report.get('terminal_repeats_added',0)
            repeat_report['repeat_candidates']+=report['repeat_candidates']
            repeat_report['repeat_review_candidates'].extend({**item,'start':start+item['start'],'end':start+item['end']} for item in report['repeat_review_candidates'])
            existing_ids={r.get('id') for r in local_rows}
            pending=[]
            for row in expanded:
                if (row.get('id') or '').startswith('auto-repeat:') and row.get('id') not in existing_ids:
                    pending.append(row);continue
                index=row['_original_index'];before[index]=pending;pending=[];replacements[index]=row
            if pending:after[indices[-1]]=pending
            words=[{'word':t} for row in expanded for t in row['text'].split() if spoken(t)]
            normalized=normalized_words(words,vocab);targets=[vocab[c] for c in '|'.join(normalized)]
            emission=emissions[0]
            emit(.96*(block_index+.90)/len(blocks),'Tüm dönüşler yerleştirildi; kelimeler bağlanıyor…')
            evidence=(1-emission[0,:,vocab.get('[PAD]',0)].exp()).numpy()>.35
            voice_regions.extend([start+a,start+b] for a,b in regions(evidence,min_length=.02,bridge=.45))
            path,scores=AF.forced_align(emission,torch.tensor([targets],dtype=torch.int32),blank=vocab.get('[PAD]',0))
            spans=AF.merge_tokens(path[0],scores[0].exp(),blank=vocab.get('[PAD]',0))
            aligned=words_from_spans(words,normalized,spans,targets,hop/16000,start)
            for word in aligned:word['end']=min(end,word['end'])
            rescue_weak_words(audio,rate,start,end,aligned,model,extractor,vocab,device,
                lambda p,message:emit(.96*(block_index+.95)/len(blocks),message))
            repeat_report['repaired_word_spans']+=repair_anomalous_words(aligned,expanded,vocab,start,end)
            repeat_report['uncertain_word_repairs']=repeat_report.get('uncertain_word_repairs',0)+rescue_weak_words(
                audio,rate,start,end,aligned,model,extractor,vocab,device,
                lambda p,message:emit(.96*(block_index+.97)/len(blocks),message),threshold=.5)
            local_completed.append((expanded,aligned))
        rows=[]
        for i,row in enumerate(original_rows):
            rows.extend(before.get(i,[]));rows.append(replacements.get(i,row));rows.extend(after.get(i,[]))
        if len(rows)>500:raise ValueError('Tekrarlarla birlikte 500 satır sınırı aşıldı; mevcut sözler korundu.')
        positions={id(row):index for index,row in enumerate(rows)}
        completed=[([positions[id(row)] for row in expanded],aligned) for expanded,aligned in local_completed]
        for row in rows:row.pop('_original_index',None);row.pop('_occurrence_words',None);row.pop('_terminal_occurrence',None)
        emit(.98,'Satır sırası, dönüşler ve ara müzikler kontrol ediliyor…')
        return finish(completed)
    finally:
        del model
        if device=='cuda':torch.cuda.empty_cache()


def choose_boundary_candidate(original,candidates,lower,upper):
    """Require corroborated local boundaries before clearing an uncertainty flag."""
    usable=[w for w in candidates if w['probability']>=.5 and lower<=w['start']<w['end']<=upper]
    pairs=[(a,b) for i,a in enumerate(usable) for b in usable[i+1:]
           if a.get('recovery_channel')!=b.get('recovery_channel')
           and abs(a['start']-b['start'])<=.16 and abs(a['end']-b['end'])<=.16]
    if not pairs:return original
    a,b=max(pairs,key=lambda pair:min(w['probability'] for w in pair))
    return {**original,'start':(a['start']+b['start'])/2,'end':(a['end']+b['end'])/2,
            'probability':min(a['probability'],b['probability']),'needs_review':False,
            'timing_source':'ctc','recovery_channel':'local_consensus'}


def rescue_weak_words(audio,rate,start,end,words,model,extractor,vocab,device,progress,threshold=.1):
    """Retry only rejected words in a local phrase, never relaxing acceptance."""
    import torch
    import torchaudio.functional as AF
    from karaoke_ctc import normalized_words,words_from_spans
    repaired=0
    for index,word in enumerate(words):
        if word.get('timing_source')=='manual' and not word.get('needs_review'):continue
        if word['probability']>=threshold and not (threshold>.1 and word.get('needs_review')):continue
        progress(.86,'Belirsiz kelime, komşularıyla ve ses kanallarıyla kontrol ediliyor…')
        first=max(0,index-1);last=min(len(words),index+2)
        phrase=words[first:last]
        a=max(start,phrase[0]['start']-.25);b=min(end,phrase[-1]['end']+.35)
        if b<=a:continue
        original=copy.deepcopy(word);best=original;candidates=[]
        lower=words[index-1]['end'] if index else start
        upper=words[index+1]['start'] if index+1<len(words) else end
        normalized=normalized_words(phrase,vocab);targets=[vocab[c] for c in '|'.join(normalized)]
        for channel in ('mix','left','right'):
            clip=audio[round((a-start)*rate):round((b-start)*rate)]
            if not len(clip):continue
            mono=clip.mean(axis=1) if channel=='mix' else clip[:,0 if channel=='left' else min(1,clip.shape[1]-1)]
            wave=AF.resample(torch.from_numpy(mono.copy()),rate,16000)
            if len(wave)<400:continue
            inputs=extractor(wave.numpy(),sampling_rate=16000,return_tensors='pt')
            with torch.inference_mode():
                emission=model(**{k:v.to(device) for k,v in inputs.items()}).logits.log_softmax(-1).cpu()
            try:
                path,scores=AF.forced_align(emission,torch.tensor([targets],dtype=torch.int32),blank=vocab.get('[PAD]',0))
                spans=AF.merge_tokens(path[0],scores[0].exp(),blank=vocab.get('[PAD]',0))
                candidate=words_from_spans(phrase,normalized,spans,targets,.02,a)[index-first]
            except (ValueError,RuntimeError):continue
            lower=words[index-1]['end'] if index else start
            upper=words[index+1]['start'] if index+1<len(words) else end
            candidates.append({**candidate,'recovery_channel':channel})
            if lower<=candidate['start']<candidate['end']<=upper and candidate['probability']>best['probability']:
                best={**candidate,'recovery_channel':channel}
        if threshold>.1:
            best=choose_boundary_candidate(original,candidates,lower,upper)
        if best!=original:repaired+=1
        words[index]=best
    return repaired


def repair_anomalous_words(aligned,rows,vocab,start,end):
    """An independent occurrence window may repair a word stretched over a break."""
    from karaoke_ctc import normalized_words
    cursor=0;repaired=0
    for row in rows:
        tokens=[t for t in row['text'].split() if spoken(t)]
        proposal=row.get('_occurrence_words') or []
        original=row.get('words') or []
        if len(proposal)!=len(tokens):cursor+=len(tokens);continue
        if normalized_words([{'word':t} for t in tokens],vocab)!=normalized_words(proposal,vocab):
            cursor+=len(tokens);continue
        for index,alternative in enumerate(proposal):
            word=aligned[cursor+index]
            manual=next((w for w in original if w.get('word')==tokens[index] and w.get('timing_source')=='manual'
                         and not w.get('needs_review') and w['end']>w['start']),None)
            if manual:continue
            terminal=row.get('_terminal_occurrence',False)
            if not terminal and word['end']-word['start']<=6:continue
            a=start+alternative['start'];b=start+alternative['end']
            lower=aligned[cursor+index-1]['end'] if cursor+index else start
            upper=aligned[cursor+index+1]['start'] if cursor+index+1<len(aligned) else end
            if lower<=a<b<=upper and (terminal or b-a<(word['end']-word['start'])*.6) and alternative['probability']>=.1:
                aligned[cursor+index]={**word,'start':a,'end':b,'probability':alternative['probability'],
                                      'needs_review':alternative.get('needs_review',False) or alternative['probability']<.5,'timing_source':'ctc'}
                repaired+=1
        cursor+=len(tokens)
    return repaired
