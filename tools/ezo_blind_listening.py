"""Prepare a human listening comparison; never invent listener preferences."""
import argparse
import hashlib
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
import json
from pathlib import Path
import secrets
import threading
import numpy as np
import soundfile as sf

ROOT=Path(__file__).resolve().parents[1]
CRITERIA=['drums','bass','music','voice']
CLIPS=[(40,56),(84,96),(140,156),(220,236),(265,281)]

HTML='''<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ezo · Kör dinleme karşılaştırması</title><style>
:root{color-scheme:dark;font-family:system-ui;background:#14121c;color:#f2effa}body{max-width:1000px;margin:36px auto;padding:0 22px}h1{font-size:30px;margin-bottom:8px}p{line-height:1.6;color:#c5bfd5}.card{background:#211d2e;border:1px solid #443858;border-radius:18px;padding:22px;margin:20px 0}button,select{font:inherit;border:1px solid #66567e;background:#30273e;color:#fff;border-radius:10px;padding:11px 16px;cursor:pointer}button.active{background:#8060b5;border-color:#c6a3ff}button:hover{border-color:#d3b3ff}button:disabled{opacity:.45;cursor:default}.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:15px 0}.grow{flex:1}#seek{width:100%;accent-color:#b08be9}small{color:#b9afca}.rating{display:flex;gap:15px;align-items:center;border-top:1px solid #42364f;padding:15px 0;flex-wrap:wrap}.rating strong{flex:1;min-width:230px}.choices{display:flex;gap:8px;flex-wrap:wrap}.choices button{padding:9px 14px}#results{white-space:pre-wrap;line-height:1.7}a{color:#d4b3ff}.tag{color:#d0afff;font-size:13px}#error{color:#ffb5b5}#saved{min-height:22px}label{color:#cfc4df}
</style><body><span class="tag">AYNI ŞARKI · AYNI ZAMAN · GİZLİ PRESET İSİMLERİ</span><h1>Ezo · V1 / yeni V2 dinleme testi</h1>
<p>A ve B her bölümde rastgele atanır. Hangisinin V1 olduğunu sonuçları açana kadar görmezsin. İki enstrümanın RMS seviyeleri eşleştirildi; EQ, kompresör veya limiter eklenmedi. Kararı sadece dinleyerek ver.</p>
<div class="card"><label for="clip">Dinlenecek bölüm</label><div class="row"><select id="clip" class="grow"></select><span id="ready">Yükleniyor…</span></div>
<div class="row"><button id="play">▶ Oynat</button><button class="switch active" data-id="A">A</button><button class="switch" data-id="B">B</button><button class="switch" data-id="O">Orijinal kayıt</button><span id="time" class="grow">0:00</span></div><input aria-label="Dinleme konumu" id="seek" type="range" min="0" max="1" step="0.01" value="0">
<p><small>A ↔ B geçişi aynı zaman noktasında yapılır. Orijinal kayıt vokal içerir; izole enstrüman referansı değildir. Önce davul atağı ve bas notalarının kuyruğunu, sonra telli/diğer enstrümanların doğallığını ve kalan insan sesini karşılaştır. Fark duyamıyorsan “Fark yok”; karar veremiyorsan “Kararsız” seç.</small></p>
<div id="ratings"></div><div id="saved"><small>Henüz bir dinleme tercihi kaydedilmedi.</small></div></div>
<div class="card"><h2>Dinleme sonucu</h2><p>Program ses kalitesini kendi başına puanlamaz. Burada yalnızca senin seçimlerin değerlendirilir; sayısal model ölçümleri tercihini etkilememesi için gösterilmez.</p><div class="row"><button id="reveal">Seçimlerimi değerlendir ve presetleri göster</button><button id="download">Tercihlerimi indir</button></div><div id="results">Henüz dinleme sonucu yok.</div></div>
<p id="error"></p><p><small>Başlangıçta presetler ve mevcut çıktılar değiştirilmez. Tercihler yalnız bu bilgisayara kaydedilir. Test tamamlanmadan bir kazanan veya “sıfır sızıntı” sonucu üretilmez.</small></p>
<script>
let manifest,ctx,buffers={},sources={},gains={},playing=false,offset=0,started=0,selected='A',generation=0,answers={},revealed=false;
const $=id=>document.getElementById(id),names={drums:'Davul atakları daha doğal / net',bass:'Bas notaları ve kuyrukları daha doğal',music:'Enstrüman ayrıntısı daha doğal, artefakt daha az',voice:'Kalan vokal sesi daha az'};
const index=()=>Number($('clip').value),fmt=n=>`${Math.floor(n/60)}:${String(Math.floor(n%60)).padStart(2,'0')}`;
const pos=()=>playing?Math.min(buffers.A?.duration||0,offset+ctx.currentTime-started):offset;
function stop(){if(playing)offset=pos();playing=false;for(const s of Object.values(sources)){try{s.stop()}catch{}}sources={};$('play').textContent='▶ Oynat'}
function applyGains(){if(!ctx)return;for(const [id,g] of Object.entries(gains)){g.gain.cancelScheduledValues(ctx.currentTime);g.gain.setValueAtTime(g.gain.value,ctx.currentTime);g.gain.linearRampToValueAtTime(id===selected?1:0,ctx.currentTime+.02)}}
async function play(){try{if(!buffers.A)return;if(playing){stop();return}await ctx.resume();if(offset>=buffers.A.duration-.03)offset=0;started=ctx.currentTime+.04;for(const id of ['A','B','O']){const s=ctx.createBufferSource(),g=ctx.createGain();s.buffer=buffers[id];g.gain.value=id===selected?1:0;s.connect(g);g.connect(ctx.destination);s.start(started,offset);sources[id]=s;gains[id]=g}playing=true;$('play').textContent='Ⅱ Duraklat'}catch(e){$('error').textContent=e.message}}
async function load(){const gen=++generation;stop();offset=0;buffers={};$('ready').textContent='Sesler yükleniyor…';$('play').disabled=true;renderRatings();try{ctx??=new AudioContext();const c=manifest.clips[index()];const result=await Promise.all(['A','B','O'].map(async id=>{const r=await fetch(c.files[id]);if(!r.ok)throw Error('Ses dosyası açılamadı');return [id,await ctx.decodeAudioData(await r.arrayBuffer())]}));if(gen!==generation)return;buffers=Object.fromEntries(result);$('seek').max=buffers.A.duration;$('ready').textContent='Hazır · RMS eşleştirilmiş';$('play').disabled=false}catch(e){$('ready').textContent='Yükleme hatası';$('error').textContent=e.message}}
function renderRatings(){const values=answers[index()]||{};$('ratings').replaceChildren();for(const [key,title] of Object.entries(names)){const row=document.createElement('div');row.className='rating';const label=document.createElement('strong');label.textContent=title;row.append(label);const options=document.createElement('div');options.className='choices';for(const [value,text] of [['A','A daha iyi'],['B','B daha iyi'],['tie','Fark yok'],['unsure','Kararsız']]){const b=document.createElement('button');b.textContent=text;if(values[key]===value)b.className='active';b.onclick=()=>{answers[index()]??={};answers[index()][key]=value;renderRatings();save()};options.append(b)}row.append(options);$('ratings').append(row)}}
async function save(){try{const r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({test_id:manifest.test_id,answers})});if(!r.ok)throw Error('Tercihler kaydedilemedi');$('saved').textContent='Tercihlerin bu bilgisayara kaydedildi.';if(revealed)$('results').textContent='Tercihler değişti. Güncel değerlendirme için sonuç düğmesine tekrar bas.'}catch(e){$('error').textContent=e.message}}
$('play').onclick=play;$('clip').onchange=load;for(const b of document.querySelectorAll('.switch'))b.onclick=()=>{selected=b.dataset.id;for(const x of document.querySelectorAll('.switch'))x.classList.toggle('active',x===b);applyGains()};$('seek').oninput=async()=>{const resume=playing;stop();offset=Number($('seek').value);if(resume)await play()};
$('reveal').onclick=async()=>{try{const r=await fetch('/reveal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({test_id:manifest.test_id,answers})});const data=await r.json();if(!r.ok)throw Error(data.error);revealed=true;$('results').textContent=data.text}catch(e){$('error').textContent=e.message}};
$('download').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify({test_id:manifest.test_id,answers,labels_revealed:revealed},null,2)],{type:'application/json'}));a.download='Ezo-dinleme-tercihlerim.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)};
function frame(){if(playing){if(ctx.currentTime>=started){$('seek').value=pos();$('time').textContent=`${fmt(pos())} / ${fmt(buffers.A.duration)}`;}if(pos()>=buffers.A.duration)stop()}else if(buffers.A){$('seek').value=offset;$('time').textContent=`${fmt(offset)} / ${fmt(buffers.A.duration)}`}requestAnimationFrame(frame)}frame();
(async()=>{try{manifest=await(await fetch('manifest.json')).json();for(const [i,c] of manifest.clips.entries()){const o=document.createElement('option');o.value=i;o.textContent=`Bölüm ${i+1} · ${c.start}–${c.end}. saniye`;$('clip').append(o)}const state=await(await fetch('/state')).json();answers=state.answers||{};revealed=!!state.revealed;await load()}catch(e){$('error').textContent=e.message}})();
</script></body></html>'''


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    test_id=secrets.token_hex(4)
    folder=ROOT/'outputs'/f'Ezo_Kor_Dinleme_{test_id}';folder.mkdir()
    private=ROOT/'cache/ezo_listening';private.mkdir(exist_ok=True)
    report=json.loads((ROOT/'outputs/Ezo_Music_Refined/v1-vs-final-v2-recheck.json').read_text(encoding='utf8'))
    paths={key:Path(value['file']) for key,value in report['systems'].items()}
    for key,path in paths.items():assert digest(path)==report['systems'][key]['sha256']
    original=next((ROOT/'ytdl').glob('Nurettin*Ezo.wav'))
    assert digest(original)==report['source_sha256']
    manifest={'test_id':test_id,'clips':[]};key={'test_id':test_id,'folder':str(folder),'clips':[],'inputs':report['systems']}
    for number,(start,end) in enumerate(CLIPS,1):
        waves={}
        for name,path in {**paths,'original':original}.items():
            x,rate=sf.read(path,start=start*44100,stop=end*44100,always_2d=True)
            assert rate==44100 and x.shape==((end-start)*rate,2) and np.isfinite(x).all()
            waves[name]=x
        rms={name:float(np.sqrt(np.mean(waves[name]**2))) for name in paths}
        target=min(rms.values());level={name:target/max(value,1e-15) for name,value in rms.items()}
        peak=max(float(np.abs(waves[name]*level[name]).max()) for name in paths)
        common=min(1.,.89/max(peak,float(np.abs(waves['original']).max()),1e-15))
        assignment=['v1','new_v2']
        if secrets.randbelow(2):assignment.reverse()
        mapping=dict(zip(['A','B'],assignment));files={}
        for label,name in {**mapping,'O':'original'}.items():
            filename=f'{number}_{label}.wav';files[label]=filename
            sf.write(folder/filename,waves[name]*level.get(name,1.)*common,rate,subtype='PCM_24')
        a,_=sf.read(folder/files['A'],always_2d=True);b,_=sf.read(folder/files['B'],always_2d=True)
        match_db=float(20*np.log10(np.sqrt(np.mean(a*a))/np.sqrt(np.mean(b*b))))
        assert abs(match_db)<.001
        manifest['clips'].append({'start':start,'end':end,'files':files})
        key['clips'].append({'start':start,'end':end,'assignment':mapping,'rms_match_error_db':match_db,
                             'gain_db':{name:float(20*np.log10(gain*common)) for name,gain in level.items()}})
    (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    (folder/'index.html').write_text(HTML,encoding='utf8')
    key_path=private/f'{test_id}-key.json';key_path.write_text(json.dumps(key,ensure_ascii=False,indent=2),encoding='utf8')
    result_path=private/f'{test_id}-results.json'
    result_path.write_text(json.dumps({'test_id':test_id,'answers':{},'revealed':False,'status':'awaiting_human_preferences'},indent=2),encoding='utf8')
    print(json.dumps({'folder':str(folder),'key':str(key_path),'results':str(result_path),'clips':len(CLIPS),'rms_match_tolerance_db':.001}),flush=True)


def serve(key_path,port):
    key=json.loads(Path(key_path).read_text(encoding='utf8'));folder=Path(key['folder'])
    state_path=Path(key_path).with_name(key['test_id']+'-results.json');lock=threading.Lock()
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(folder),**kwargs)
        def response(self,data,status=200):
            body=json.dumps(data,ensure_ascii=False).encode();self.send_response(status)
            self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
        def do_GET(self):
            if self.path=='/state':
                with lock:state=json.loads(state_path.read_text(encoding='utf8'))
                self.response(state);return
            super().do_GET()
        def do_POST(self):
            if self.path not in ('/save','/reveal'):self.response({'error':'Bilinmeyen işlem'},404);return
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<16000:raise ValueError('Geçersiz veri boyutu')
                data=json.loads(self.rfile.read(size));assert data['test_id']==key['test_id']
                answers=data['answers'];assert isinstance(answers,dict)
                for index,criteria in answers.items():
                    assert str(int(index))==index and 0<=int(index)<len(key['clips']) and isinstance(criteria,dict)
                    assert all(k in CRITERIA and v in ('A','B','tie','unsure') for k,v in criteria.items())
                with lock:
                    state=json.loads(state_path.read_text(encoding='utf8'))
                    state['answers']=answers;state['status']='human_preferences_entered' if any(answers.values()) else 'awaiting_human_preferences'
                    if self.path=='/reveal':
                        if not any(answers.values()):raise ValueError('Henüz tercih girilmedi. Dinleyip seçim yap; fark yoksa bunu seçebilirsin.')
                        state['revealed']=True
                    temp=state_path.with_suffix('.tmp');temp.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8');temp.replace(state_path)
                if self.path=='/save':self.response({'saved':True});return
                lines=['Senin dinleme tercihlerinin özeti (otomatik ses kalitesi puanı değildir):','']
                for criterion,title in zip(CRITERIA,['Davul','Bas','Enstrüman doğallığı','Daha az vokal']):
                    counts={'v1':0,'new_v2':0,'tie':0,'unsure':0}
                    for index,criteria in answers.items():
                        value=criteria.get(criterion)
                        if value:counts[key['clips'][int(index)]['assignment'][value] if value in ('A','B') else value]+=1
                    lines.append(f"{title}: V1 {counts['v1']} · yeni V2 {counts['new_v2']} · fark yok {counts['tie']} · kararsız {counts['unsure']}")
                lines+=['','Bölüm anahtarı:']
                for i,clip in enumerate(key['clips'],1):
                    pretty=lambda name:'V1' if name=='v1' else 'yeni V2'
                    lines.append(f"{i}. bölüm: A = {pretty(clip['assignment']['A'])}, B = {pretty(clip['assignment']['B'])}")
                lines+=['','İsimler artık açık. Aynı testte sonraki seçimler kör değerlendirme sayılmaz. Beş kısa bölüm, tüm şarkıda üstünlük veya sıfır kayıp kanıtı değildir.']
                self.response({'text':'\n'.join(lines)})
            except Exception as e:self.response({'error':str(e) or 'Geçersiz tercih verisi'},400)
    print(f'Listening test ready: http://127.0.0.1:{port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','serve']);parser.add_argument('--key');parser.add_argument('--port',type=int,default=8766);args=parser.parse_args()
    if args.mode=='prepare':prepare()
    else:serve(args.key,args.port)
