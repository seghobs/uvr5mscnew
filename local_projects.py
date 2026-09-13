"""Atomic, versioned local project data. Browser storage is only a mirror."""
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import uuid


class ProjectStore:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.RLock()

    @staticmethod
    def identity(key):
        if key.startswith('uvr-passages-v3:'):
            return key[len('uvr-passages-v3:'):].rsplit(':',1)[0]
        if key.startswith('uvr-passages-v2:'):
            return key[len('uvr-passages-v2:'):].rsplit(':', 2)[0]
        for prefix in ('uvr-stem-settings:', 'uvr-history:', 'uvr-lyrics-draft:', 'lyrics:', 'project:'):
            if key.startswith(prefix): return key[len(prefix):]
        return '_workspace'

    def path(self, key):
        owner = self.identity(key)
        folder = self.root / hashlib.sha256(owner.encode()).hexdigest()[:24]
        return folder / (hashlib.sha256(key.encode()).hexdigest() + '.json')

    def put(self, key, value, only_missing=False):
        if not isinstance(key, str) or not 1 <= len(key) <= 1024:
            raise ValueError('Invalid project key')
        record = {'key': key, 'owner': self.identity(key), 'value': value, 'updated_at': time.time()}
        encoded = json.dumps(record, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode()) > 16*1024*1024: raise ValueError('Project entry too large')
        with self.lock:
            path = self.path(key)
            if only_missing and path.exists(): return self.get(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.tmp-'+uuid.uuid4().hex)
            try:
                with temporary.open('w', encoding='utf-8') as handle:
                    handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
                if path.exists():
                    backup = path.with_suffix('.previous')
                    # Keep the last known complete revision, without moving the live file.
                    import shutil
                    shutil.copyfile(path, backup)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            if key=='uvr_library' and isinstance(value,str):
                items=json.loads(value)
                seen=set(self.get('_library_seen') or [])
                seen.update(str(item.get('id')) for item in items if isinstance(item,dict))
                self.put('_library_seen',sorted(seen))
                for item in items:
                    if isinstance(item,dict) and item.get('id'):
                        manifest=dict(item)
                        manifest['audio_files']=[{'file':stem,'relative_path':'../../outputs/'+Path(stem).name} for stem in item.get('stems',[]) if isinstance(stem,str)]
                        manifest['related_folders']={stem:str(self.path('lyrics:'+stem).parent.relative_to(self.root)) for stem in item.get('stems',[]) if isinstance(stem,str)}
                        self.put('project:'+str(item['id']),manifest)
            return value

    def update_library(self,value,removed_ids=()):
        # Writes from an older tab may add/update items, but can only delete IDs it explicitly names.
        incoming=json.loads(value or '[]')
        if not isinstance(incoming,list) or any(not isinstance(item,dict) or 'id' not in item for item in incoming):
            raise ValueError('Invalid library data')
        with self.lock:
            current=json.loads(self.get('uvr_library') or '[]')
            removed={str(identifier) for identifier in removed_ids}
            by_id={str(item['id']):item for item in current if str(item['id']) not in removed}
            for item in incoming:by_id[str(item['id'])]=item
            merged=json.dumps(list(by_id.values()),ensure_ascii=False)
            self.put('uvr_library',merged)
            return merged

    def migrate(self,key,value):
        with self.lock:
            if key=='uvr_library' and self.path(key).exists():
                current=json.loads(self.get(key) or '[]')
                seen=set(self.get('_library_seen') or [])
                incoming=json.loads(value)
                missing=[item for item in incoming if isinstance(item,dict) and str(item.get('id')) not in seen]
                if missing:self.put(key,json.dumps(current+missing,ensure_ascii=False))
                return
            self.put(key,value,only_missing=True)

    def get(self, key):
        with self.lock:
            path = self.path(key)
            for candidate in (path, path.with_suffix('.previous')):
                try: return json.loads(candidate.read_text(encoding='utf-8'))['value']
                except (FileNotFoundError, ValueError, KeyError): pass
            return None

    def all(self):
        with self.lock:
            result = {}
            for path in self.root.glob('*/*.json'):
                for candidate in (path,path.with_suffix('.previous')):
                    try:
                        record=json.loads(candidate.read_text(encoding='utf-8'))
                        result[record['key']]=record['value']; break
                    except (ValueError, KeyError, OSError): pass
            return result
