"""Explicit, pinned language-specific CTC models; no silent language fallback."""
import json
import re
from pathlib import Path


MMS_ADAPTERS = {'kmr_mms':'kmr-script_latin', 'tr_mms':'tur', 'az':'azj-script_latin', 'en':'eng'}


class AlignmentVocabulary(dict):
    def __init__(self, values, language):
        super().__init__(values)
        self.language = language


def resolve_language(language, rows):
    code = (language or 'auto').lower()
    if code in ('ku', 'kur', 'kmr'): return 'kmr'
    if code in ('az', 'aze', 'azj'): return 'az'
    if code in ('en', 'eng'): return 'en'
    if code == 'tr': return 'tr'
    if code != 'auto':
        raise ValueError('Bu dil için doğrulanmış söz hizalama modeli henüz eklenmedi. Senkron dilini Türkçe, Kurmancî, Azerbaycanca veya İngilizce seçin.')
    # Conservative lyrics evidence, not the filename or the singer's identity.
    text = ' '.join(r['text'] for r in rows).replace('İ', 'i').lower()
    tokens = set(re.findall(r'[^\W\d_]+', text))
    if 'ə' in text: return 'az'
    english = tokens & {'the','you','your','my','love','and','with','never','me','it','is','to','of'}
    if len(english) >= 4 and not any(c in text for c in 'çğıöşüêîû'): return 'en'
    markers = tokens & {'ez', 'tu', 'ji', 'jî', 'û', 'vê', 'xew', 'bûye', 'dil', 'diêşe', 'dêşe', 'te', 'min', 'li', 'şev', 'roj', 'bê', 'dîn'}
    return 'kmr' if len(markers) >= 4 and any(c in text for c in 'êîû') else 'tr'


def model_spec(language):
    from karaoke_ctc import MODEL_DIR, MODEL_ID, MODEL_REVISION
    if language == 'tr': return MODEL_DIR, MODEL_ID, MODEL_REVISION
    if language == 'en_lv60':
        return (Path(__file__).resolve().parent / 'models/alignment/english-lv60-ctc',
                'facebook/wav2vec2-large-960h-lv60-self','54074b1c16f4de6a5ad59affb4caa8f2ea03a119')
    if language == 'tr_cv8':
        return (Path(__file__).resolve().parent / 'models/alignment/turkish-cv8-ctc',
                'mpoyraz/wav2vec2-xls-r-300m-cv8-turkish','bdd0bb878d8bf59509611631e334eb073ba57773')
    if language == 'kmr':
        return (Path(__file__).resolve().parent / 'models/alignment/kurmanji-cv8-ctc',
                'maniwebdev/xlsr_kurmanji_kurdish_custom',
                'c171cb167646a94f29ec716b510c57e33eb15c3f')
    if language in MMS_ADAPTERS:
        return (Path(__file__).resolve().parent / 'models/alignment/mms-ctc',
                'facebook/mms-1b-all','3d33597edbdaaba14a8e858e2c8caa76e3cec0cd')
    raise ValueError('Desteklenmeyen hizalama dili: ' + str(language))


def ensure_model(language, progress=None):
    directory, repo, revision = model_spec(language)
    weights='pytorch_model.bin' if language in ('tr','tr_cv8','en_lv60') else 'model.safetensors'
    files=['config.json','preprocessor_config.json','vocab.json',weights,'README.md']
    adapter=MMS_ADAPTERS.get(language)
    if adapter:files.append(f'adapter.{adapter}.safetensors')
    if not all((directory / f).is_file() for f in files if f!='README.md'):
        if progress: progress(0, f'{"Türkçe" if language.startswith("tr") else {"az":"Azerbaycanca","en":"İngilizce","en_lv60":"İngilizce"}.get(language,"Kurmancî")} hizalama modeli indiriliyor…')
        from huggingface_hub import snapshot_download
        snapshot_download(repo, revision=revision, local_dir=str(directory),
                          allow_patterns=files)
    vocab=json.loads((directory / 'vocab.json').read_text(encoding='utf-8'))
    if language == 'en_lv60':
        # The English checkpoint emits uppercase labels; keep acoustic_text's
        # lowercase targets mapped to the original, unchanged logit indices.
        vocab={key.lower():value for key,value in vocab.items()}
        vocab['[PAD]']=vocab['<pad>']
    if adapter:
        vocab=vocab[adapter];vocab['[PAD]']=vocab['<pad>']
    return directory, AlignmentVocabulary(vocab, {'kmr_mms':'kmr','tr_mms':'tr','tr_cv8':'tr','en_lv60':'en'}.get(language,language))
