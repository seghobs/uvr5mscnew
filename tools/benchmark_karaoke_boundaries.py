import hashlib,json,pathlib,sys,urllib.request
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import argparse
p=argparse.ArgumentParser(description='Paired English CTC benchmark; fixed oracle windows and 80ms tolerance')
p.add_argument('--metadata',required=True,help='JamendoLyrics three-record metadata JSON')
p.add_argument('--audio-dir',required=True,help='Directory containing sample.mp3, sample-1.mp3, sample-2.mp3; missing files download from official dataset')
p.add_argument('--output',required=True)
args=p.parse_args()
from karaoke_ctc import refine_ctc
from karaoke_inference import RefinementSession
from karaoke_alignment_benchmark import score_alignment
meta=json.load(open(args.metadata,encoding='utf8'));root=pathlib.Path(args.audio_dir);root.mkdir(parents=True,exist_ok=True);result=[]
for index,song in enumerate(meta):
 path=root/('sample.mp3' if index==0 else 'sample-'+str(index)+'.mp3')
 if not path.is_file():urllib.request.urlretrieve('https://huggingface.co/datasets/jamendolyrics/jamendolyrics/resolve/main/subsets/en/'+song['file_name'],path)
 digest=hashlib.sha256(path.read_bytes()).hexdigest()
 for subset,lines in ([('target',song['lines'][:3]),('heldout_lines',song['lines'][3:15])] if index==0 else [('unseen_song',song['lines'][:15])]):
  gold=[];coarse=[]
  for ri,line in enumerate(lines):
   words=[w for w in song['words'] if line['start']-.001<=w['start'] and w['end']<=line['end']+.001]
   gold.append({'id':str(ri),'text':line['text'],'start':line['start'],'end':line['end'],'words':[{'word':w['text'],'start':w['start'],'end':w['end']} for w in words]})
   coarse.append({'id':str(ri),'text':line['text'],'start':max(0,line['start']-.5),'end':line['end']+.5,'words':[{'word':w['text'],'start':max(0,line['start']-.5),'end':line['end']+.5} for w in words]})
  ref={'reference_kind':'human_verified','audio_sha256':digest,'segments':gold}
  for model in ('en','en_lv60'):
   with RefinementSession() as session:
    for policy in ('characters','balanced'):
     rows=refine_ctc(str(path),coarse,model,context_padding=0,independent_rows=True,session=session,boundary_policy=policy)
     metrics=score_alignment(ref,{'audio_sha256':digest,'segments':rows},.08)
     entry={'recording':song['name'],'subset':subset,'model':model,'boundary_policy':policy,'metrics':metrics}
     result.append(entry)
     print(index,subset,model,policy,metrics['words_within_tolerance'],'/',metrics['reference_words'],round(metrics['onset_mae_seconds'],3),round(metrics['offset_mae_seconds'],3),flush=True)
     pathlib.Path(args.output).write_text(json.dumps({'reference_source':'https://huggingface.co/datasets/jamendolyrics/jamendolyrics','evaluation_mode':'same_oracle_sentence_windows_same_80ms_tolerance','runs':result},indent=2),encoding='utf8')
