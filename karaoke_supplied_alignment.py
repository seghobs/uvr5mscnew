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
    previous=0.
    for row in result:
        for word in row.get('words') or []:
            if word['end']<=word['start']:continue
            if not (math.isfinite(word['start']) and math.isfinite(word['end']) and
                    previous<=word['start']<word['end']<=duration):
                raise ValueError('Korunan elle bağlı kelimelerle çakışma bulundu; mevcut sözler değiştirilmedi.')
            previous=word['end']
    return result,{'method':'supplied_turkish_ctc','linked_words':linked,'target_words':total,
                   'review_rows':pending,'preserved_rows':sum(bool(protected(r)) for r in rows)}


def align_supplied(audio_path,rows,progress=lambda *args:None,instrumental_path=None,diagnostics=None):
    import soundfile as sf
    import torch
    import torchaudio.functional as AF
    from transformers import Wav2Vec2ForCTC,Wav2Vec2FeatureExtractor
    from karaoke_ctc import MODEL_DIR,MODEL_ID,MODEL_REVISION,normalized_words,words_from_spans
    import json
    from karaoke_interludes import generated,music_evidence,place_interludes,regions
    rows=[r for r in rows if not generated(r)]
    info=sf.info(str(audio_path));duration=info.frames/info.samplerate
    blocks=alignment_blocks(rows,duration)
    music_regions,voice_regions,available=music_evidence(audio_path,instrumental_path)
    def finish(completed):
        result,report=assemble(rows,completed,duration)
        from karaoke_repeats import expand_repeats
        result,repeat_report=expand_repeats(result,audio_path,verify_repeat if blocks else None)
        report.update(repeat_report)
        extra_words=sum(len(r.get('words') or []) for r in result if r.get('id','').startswith('auto-repeat:') and r.get('id') not in {x.get('id') for x in rows})
        report['target_words']+=extra_words;report['linked_words']+=extra_words
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
        progress(0,'Türkçe hizalama modeli indiriliyor…')
        snapshot_download(MODEL_ID,revision=MODEL_REVISION,local_dir=str(MODEL_DIR),
            allow_patterns=['config.json','preprocessor_config.json','vocab.json','pytorch_model.bin'])
    vocab=json.loads((MODEL_DIR/'vocab.json').read_text(encoding='utf8'))
    device='cuda' if torch.cuda.is_available() and torch.cuda.mem_get_info()[0]>3*1024**3 else 'cpu'
    model=Wav2Vec2ForCTC.from_pretrained(MODEL_DIR,local_files_only=True).eval().to(device)
    extractor=Wav2Vec2FeatureExtractor.from_pretrained(MODEL_DIR,local_files_only=True)
    hop=math.prod(model.config.conv_stride)
    if hop!=320:raise ValueError('Türkçe modelin zaman çözünürlüğü değişmiş.')
    def verify_repeat(row,a,b):
        progress(.98,'Verdiğiniz satırların dönüşleri sesle doğrulanıyor…')
        if any(not spoken(t) for t in row['text'].split()):return None
        from difflib import SequenceMatcher
        words=[{'word':t} for t in row['text'].split() if spoken(t)]
        normalized=normalized_words(words,vocab);targets=[vocab[c] for c in '|'.join(normalized)]
        clip,rate=sf.read(str(audio_path),start=max(0,round((a-.15)*info.samplerate)),
                          stop=min(info.frames,round((b+.15)*info.samplerate)),dtype='float32',always_2d=True)
        wave=AF.resample(torch.from_numpy(alignment_mono(clip).copy()),rate,16000)
        if len(wave)<400:return None
        inputs=extractor(wave.numpy(),sampling_rate=16000,return_tensors='pt')
        with torch.inference_mode():
            emission=model(**{k:v.to(device) for k,v in inputs.items()}).logits.log_softmax(-1).cpu()
        ids=emission[0].argmax(-1).tolist();inverse={v:k for k,v in vocab.items()}
        decoded=''.join(inverse.get(t,'') for i,t in enumerate(ids) if t!=vocab.get('[PAD]',0) and (i==0 or t!=ids[i-1]))
        if SequenceMatcher(None,decoded.replace('|',''),''.join(normalized)).ratio()<.80:return None
        try:
            path,scores=AF.forced_align(emission,torch.tensor([targets],dtype=torch.int32),blank=vocab.get('[PAD]',0))
            spans=AF.merge_tokens(path[0],scores[0].exp(),blank=vocab.get('[PAD]',0))
            verified=words_from_spans(words,normalized,spans,targets,.02,max(0,a-.15))
        except (ValueError,RuntimeError):return None
        if min(w['probability'] for w in verified)<.35 or sum(w['probability'] for w in verified)/len(verified)<.65:return None
        if any(w['end']<=w['start'] for w in verified):return None
        return verified
    completed=[]
    try:
        for block_index,(indices,start,end) in enumerate(blocks):
            words=[{'word':t} for i in indices for t in rows[i]['text'].split() if spoken(t)]
            normalized=normalized_words(words,vocab)
            targets=[vocab[c] for c in '|'.join(normalized)]
            if not targets:continue
            audio,rate=sf.read(str(audio_path),start=round(start*info.samplerate),stop=round(end*info.samplerate),
                               dtype='float32',always_2d=True)
            wave=AF.resample(torch.from_numpy(alignment_mono(audio).copy()),rate,16000)
            emissions=[];offset=0;core=16*16000;context=16000
            # Bounded GPU memory; overlap supplies context, but every frame is
            # included exactly once on the full-song timeline.
            while offset<len(wave):
                left=max(0,offset-context);right=min(len(wave),offset+core+context)
                progress(.85*((block_index+(offset/max(1,len(wave))))/len(blocks)),
                    f'Sözler sesle eşleştiriliyor · {start+offset/16000:.0f}/{duration:.0f} sn')
                clip=wave[left:right]
                if len(clip)<400:break
                inputs=extractor(clip.numpy(),sampling_rate=16000,return_tensors='pt')
                with torch.inference_mode():
                    logits=model(**{k:v.to(device) for k,v in inputs.items()}).logits.log_softmax(-1).cpu()
                first=(offset-left)//hop
                last=first+core//hop if offset+core<len(wave) else logits.shape[1]
                emissions.append(logits[:,first:last]);offset+=core
            if not emissions:raise ValueError('Ses hizalama için çok kısa.')
            emission=torch.cat(emissions,dim=1).contiguous()
            progress(.85*((block_index+.99)/len(blocks)),'Kelimelerin başlangıç ve bitişleri bağlanıyor…')
            evidence=(1-emission[0,:,vocab.get('[PAD]',0)].exp()).numpy()>.35
            voice_regions.extend([start+a,start+b] for a,b in regions(evidence,min_length=.02,bridge=.45))
            path,scores=AF.forced_align(emission,torch.tensor([targets],dtype=torch.int32),blank=vocab.get('[PAD]',0))
            spans=AF.merge_tokens(path[0],scores[0].exp(),blank=vocab.get('[PAD]',0))
            aligned=words_from_spans(words,normalized,spans,targets,hop/16000,start)
            for word in aligned:word['end']=min(end,word['end'])
            rescue_weak_words(audio,rate,start,end,aligned,model,extractor,vocab,device,
                lambda p,message:progress(.85*(block_index+.995)/len(blocks),message))
            completed.append((indices,aligned))
        progress(.98,'Satır sırası ve ara müzikler kontrol ediliyor…')
        return finish(completed)
    finally:
        del model
        if device=='cuda':torch.cuda.empty_cache()


def rescue_weak_words(audio,rate,start,end,words,model,extractor,vocab,device,progress):
    """Retry only rejected words in a local phrase, never relaxing acceptance."""
    import torch
    import torchaudio.functional as AF
    from karaoke_ctc import normalized_words,words_from_spans
    for index,word in enumerate(words):
        if word['probability']>=.10:continue
        progress(.86,'Belirsiz kelime, komşularıyla ve ses kanallarıyla kontrol ediliyor…')
        first=max(0,index-1);last=min(len(words),index+2)
        phrase=words[first:last]
        a=max(start,phrase[0]['start']-.25);b=min(end,phrase[-1]['end']+.35)
        if b<=a:continue
        original=copy.deepcopy(word);best=original
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
            if lower<=candidate['start']<candidate['end']<=upper and candidate['probability']>best['probability']:
                best={**candidate,'recovery_channel':channel}
        words[index]=best
