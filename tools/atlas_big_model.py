"""Additional pinned MelBand Big beta7 expert, never registers in production."""
import hashlib
import yaml
from tools import atlas_new_models as new,atlas_alternative_screen as a,atlas_extended as e
from tools.atlas_benchmark import write_json

def infer(tracks=None):
    import core
    new.assert_idle_backend()
    repo='Mel-Band-Roformer-big';revision='1508d1ed7c54cb0017b2cbfaabdaf3ca87d2cf74'
    folder=new.WORK/'16';folder.mkdir(exist_ok=True)
    checkpoint=new.download(repo,revision,'big_beta7.ckpt',folder/'big_beta7.ckpt')
    digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if digest!='9d68b9a8689a3500c45d3418a7811934e557760db07285f483088a0965b0eb88':raise RuntimeError('Big checkpoint hash mismatch')
    published=new.download(repo,revision,'big_beta7.yaml',folder/'publisher.yaml')
    config=yaml.load(published.read_text(encoding='utf8'),Loader=yaml.FullLoader)
    config['audio']['hop_length']=config['model']['stft_hop_length'];config['inference']['batch_size']=1
    path=folder/'config_mel_band_roformer.yaml';path.write_text(yaml.dump(config),encoding='utf8')
    write_json(folder/'provenance.json',{'repo':repo,'revision':revision,'checkpoint_sha256':digest,
        'publisher_config_sha256':hashlib.sha256(published.read_bytes()).hexdigest(),
        'architecture':'Installed MelBandRoformer with all publisher model parameters and strict checkpoint loading; only batch/hop metadata translated.'})
    name='Experimental pinned MelBand Big beta7';old=core.Separator.download_model_files
    def model_files(self,filename,*args,**kwargs):
        if filename==checkpoint.name:return filename,'MDXC',name,str(checkpoint),str(path)
        return old(self,filename,*args,**kwargs)
    core.Separator.download_model_files=model_files;core.roformer_models[name]=checkpoint.name
    try:
        for track in tracks or a.read(new.WORK/'plan.json')['development']:
            print('BIG EXPERT',track['name'],flush=True)
            new.assert_idle_backend()
            e.infer_one(e.prepare_reference(track),16,{'model_key':name,'estimate':'vocal'})
    finally:
        core.Separator.download_model_files=old;core.roformer_models.pop(name,None)

def configure_screen():
    from tools import atlas_new_mix_screen as screen
    screen.EXPERTS=[*screen.EXPERTS,(16,)]
    screen.WORK=new.WORK/'with_big'
    write_json(screen.WORK/'plan.json',a.read(new.WORK/'plan.json'))
    return screen

def screen_fit():
    screen=configure_screen()
    screen.screen()
    fit()

def fit():
    screen=configure_screen()
    warm=None
    prior=new.WORK/'fit/frozen.json'
    if prior.exists():
        frozen=a.read(prior)
        previous=frozen['selected']
        if not previous:
            # Warm starts are development values only; convergence and all full
            # metrics still need to pass in the new fit before any confirmation.
            feasible=[t for t in frozen['trials'] if t['content_slack_min']>=-1e-8 and t['waveform_slack_min']>=-1e-8]
            if feasible:previous=max(feasible,key=lambda t:t['development_mean_sdr_gain_db'])
        if previous:warm=previous['weights']+[[0.]*len(previous['weights'][0])]
    screen.fit(regularizations=(.01,),maxiter=100,initial_weights=warm,ftol=1e-8)

def confirm():
    from tools import atlas_new_mix_screen as screen
    screen.EXPERTS=[*screen.EXPERTS,(16,)]
    screen.WORK=new.WORK/'with_big'
    screen.confirm()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('phase',nargs='?',default='infer',choices=['infer','screen_fit','fit','confirm'])
    globals()[parser.parse_args().phase]()
