"""Explicit, pinned language-specific CTC models; no silent language fallback."""
import json
import re
from pathlib import Path


class AlignmentVocabulary(dict):
    def __init__(self, values, language):
        super().__init__(values)
        self.language = language


def resolve_language(language, rows):
    code = (language or 'auto').lower()
    if code in ('ku', 'kur', 'kmr'): return 'kmr'
    if code == 'tr': return 'tr'
    if code != 'auto':
        raise ValueError('Bu dil için doğrulanmış söz hizalama modeli henüz eklenmedi. Senkron dilini Türkçe veya Kürtçe (Kurmancî) seçin.')
    # Conservative lyrics evidence, not the filename or the singer's identity.
    text = ' '.join(r['text'] for r in rows).replace('İ', 'i').lower()
    tokens = set(re.findall(r'[^\W\d_]+', text))
    markers = tokens & {'ez', 'tu', 'ji', 'jî', 'û', 'vê', 'xew', 'bûye', 'dil', 'diêşe', 'dêşe', 'te', 'min', 'li', 'şev', 'roj', 'bê', 'dîn'}
    return 'kmr' if len(markers) >= 4 and any(c in text for c in 'êîû') else 'tr'


def model_spec(language):
    from karaoke_ctc import MODEL_DIR, MODEL_ID, MODEL_REVISION
    if language == 'tr': return MODEL_DIR, MODEL_ID, MODEL_REVISION
    if language == 'kmr':
        return (Path(__file__).resolve().parent / 'models/alignment/kurmanji-cv8-ctc',
                'maniwebdev/xlsr_kurmanji_kurdish_custom',
                'c171cb167646a94f29ec716b510c57e33eb15c3f')
    if language == 'kmr_mms':
        return (Path(__file__).resolve().parent / 'models/alignment/mms-ctc',
                'facebook/mms-1b-all','3d33597edbdaaba14a8e858e2c8caa76e3cec0cd')
    raise ValueError('Desteklenmeyen hizalama dili: ' + str(language))


def ensure_model(language, progress=None):
    directory, repo, revision = model_spec(language)
    weights='pytorch_model.bin' if language=='tr' else 'model.safetensors'
    files=['config.json','preprocessor_config.json','vocab.json',weights,'README.md']
    if language=='kmr_mms':files.append('adapter.kmr-script_latin.safetensors')
    if not all((directory / f).is_file() for f in files if f!='README.md'):
        if progress: progress(0, f'{"Türkçe" if language == "tr" else "Kurmancî"} hizalama modeli indiriliyor…')
        from huggingface_hub import snapshot_download
        snapshot_download(repo, revision=revision, local_dir=str(directory),
                          allow_patterns=files)
    vocab=json.loads((directory / 'vocab.json').read_text(encoding='utf-8'))
    if language=='kmr_mms':
        vocab=vocab['kmr-script_latin'];vocab['[PAD]']=vocab['<pad>']
    return directory, AlignmentVocabulary(vocab, 'kmr' if language=='kmr_mms' else language)
