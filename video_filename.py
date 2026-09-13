"""Readable Windows-safe video filenames, reserved without overwriting a take."""
from pathlib import Path
import re
import unicodedata


def video_stem(artist='', title='', label='', fallback='Karaoke'):
    def clean(value):
        text = unicodedata.normalize('NFC', value or '')
        text = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', ' ', text)
        text = re.sub(r'\.{2,}', ' ', text)
        return ' '.join(text.split()).strip(' .')

    name = ' - '.join(filter(None, (clean(artist), clean(title))))
    name = name or clean(fallback) or 'Karaoke'
    tag = clean(label).strip('() ').strip()
    if tag:
        name += f' ( {tag} )'
    # Leave space for a collision suffix and avoid Windows legacy path limits.
    name = name[:140].rstrip(' .')
    while len(name.encode('utf-8')) > 200:
        name = name[:-1]
    if re.match(r'^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)', name, re.I):
        name = '_' + name
    return name


def reserve_video_path(directory, **metadata):
    directory = Path(directory)
    stem = video_stem(**metadata)
    number = 1
    while True:
        suffix = '' if number == 1 else f' ({number})'
        target = directory / f'{stem}{suffix}.mp4'
        try:
            with target.open('xb'):
                pass
            return target
        except FileExistsError:
            number += 1
