import sys
import os
from local_runtime import configure_local_runtime
configure_local_runtime()
from karaoke_ctc import refine_turkish

class _NullStream:
    def write(self, text): pass
    def flush(self): pass
    def isatty(self): return False
    def fileno(self): return 0
    def readable(self): return False
    def writable(self): return True
    def seekable(self): return False

if sys.stdout is None or not hasattr(sys.stdout, 'write'):
    sys.stdout = _NullStream()
if sys.stderr is None or not hasattr(sys.stderr, 'write'):
    sys.stderr = _NullStream()
if sys.stdin is None:
    sys.stdin = _NullStream()

import re
import json
import uuid
import subprocess
import time
import threading
import html
import hashlib
from contextlib import closing
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Request, WebSocket
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict
import core
from karaoke_timing import repair_timing, timing_issues, ass_time, ass_word_tags, escape_ass, align_lyrics, render_windows

import sqlite3
from fastapi.middleware.cors import CORSMiddleware

# Suppress background popup cmd windows/tabs on Windows for ffmpeg/ffprobe/helpers/audio_separator
SUBPROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

if os.name == 'nt':
    _original_popen = subprocess.Popen
    class _SilentPopen(_original_popen):
        def __init__(self, *args, **kwargs):
            if 'creationflags' not in kwargs:
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            else:
                kwargs['creationflags'] |= subprocess.CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)
    subprocess.Popen = _SilentPopen

app = FastAPI(title="UVR5 Premium API")
from lyric_sources.api import router as lyric_catalog_router
app.include_router(lyric_catalog_router)
from local_projects import ProjectStore
project_store = ProjectStore(Path(__file__).parent / 'projects')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist BEFORE any endpoint uses them
os.makedirs("uploads", exist_ok=True)
os.makedirs("assets", exist_ok=True)
os.makedirs(core.out_dir, exist_ok=True)
UPLOAD_DIR = Path("uploads").resolve()
OUTPUT_DIR = Path(core.out_dir).resolve()
YTL_DIR = Path("ytdl").resolve()
FAVORITES_DB_PATH = Path("assets/favorites.db").resolve()
os.makedirs(YTL_DIR, exist_ok=True)

# Initialize SQLite database for model favorites, lyrics cache, and project sessions
def init_favorites_db():
    try:
        with closing(sqlite3.connect(str(FAVORITES_DB_PATH))) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS model_favorites (
                    model_name TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lyrics (
                    file_key TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    language TEXT DEFAULT 'tr',
                    segments_json TEXT NOT NULL,
                    lrc_content TEXT,
                    srt_content TEXT,
                    is_edited INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""CREATE TABLE IF NOT EXISTS lyrics_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, file_key TEXT NOT NULL,
                segments_json TEXT NOT NULL, saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.commit()
    except Exception as e:
        print(f"Error initializing SQLite DB: {e}")

init_favorites_db()

def _get_lyrics_key(file_name: str) -> str:
    base = Path(file_name).stem.lower().strip()
    return base

def get_saved_lyrics(file_name: str) -> Optional[dict]:
    init_favorites_db()
    key = _get_lyrics_key(file_name)
    candidates = [key]
    if "instrumental" in key:
        candidates.append(key.replace("instrumental", "vocals"))
        candidates.append(key.replace("instrumental", "vocal"))
    elif "inst" in key:
        candidates.append(key.replace("inst", "vocals"))
        candidates.append(key.replace("inst", "vocal"))
    elif "vocals" in key:
        candidates.append(key.replace("vocals", "instrumental"))
        candidates.append(key.replace("vocals", "inst"))
    elif "vocal" in key:
        candidates.append(key.replace("vocal", "instrumental"))
        candidates.append(key.replace("vocal", "inst"))

    try:
        with closing(sqlite3.connect(str(FAVORITES_DB_PATH))) as conn:
            cursor = conn.cursor()
            for cand in candidates:
                cursor.execute(
                    "SELECT file_key, file_name, language, segments_json, lrc_content, srt_content, is_edited, updated_at FROM lyrics WHERE file_key = ?",
                    (cand,)
                )
                row = cursor.fetchone()
                if row:
                    segments = repair_timing(json.loads(row[3]))
                    return {
                        "status": "success",
                        "cached": True,
                        "file_key": row[0],
                        "file_name": row[1],
                        "language": row[2],
                        "segments": segments,
                        "timing_issues": timing_issues(segments),
                        "lrc_content": row[4] or "",
                        "srt_content": row[5] or "",
                        "is_edited": bool(row[6]),
                        "updated_at": row[7],
                        "lrc_file": f"{Path(row[1]).stem}.lrc",
                        "srt_file": f"{Path(row[1]).stem}.srt"
                    }
    except Exception as e:
        print(f"Error querying SQLite lyrics for {file_name}: {e}")
    return None

_lyrics_data_lock = threading.RLock()


def save_lyrics_db(file_name: str, language: str, segments: list, is_edited: bool = False, allow_locked_changes: bool = False) -> dict:
    with _lyrics_data_lock:
        if not allow_locked_changes:
            previous=get_saved_lyrics(file_name)
            locked=[row for row in (previous or {}).get('segments',[]) if row.get('locked')]
            if locked:
                if any(not row.get('id') or not any(candidate.get('id')==row['id'] for candidate in segments) for row in locked):
                    segments=previous['segments']
                else:
                    by_id={row['id']:row for row in locked}
                    segments=[by_id.get(row.get('id'),row) for row in segments]
        result = _save_lyrics_db(file_name, language, segments, is_edited)
        project_store.put('lyrics:' + file_name, result)
        return result


def _save_lyrics_db(file_name: str, language: str, segments: list, is_edited: bool = False) -> dict:
    init_favorites_db()
    segments = repair_timing(segments)
    key = _get_lyrics_key(file_name)
    segments_json = json.dumps(segments, ensure_ascii=False, allow_nan=False)
    
    # Generate standard LRC and SRT strings
    lrc_lines = ["[ti:" + file_name + "]", "[ar:UVR5 AI Studio]"]
    srt_lines = []
    
    for i, s in enumerate(segments):
        start_sec = float(s.get("start", 0))
        end_sec = float(s.get("end", 0))
        text = str(s.get("text", "")).strip()
        
        mins = int(start_sec // 60)
        secs = start_sec % 60
        lrc_lines.append(f"[{mins:02d}:{secs:05.2f}]{text}")
        
        st_h, st_m, st_s = int(start_sec // 3600), int((start_sec % 3600) // 60), start_sec % 60
        en_h, en_m, en_s = int(end_sec // 3600), int((end_sec % 3600) // 60), end_sec % 60
        st_str = f"{st_h:02d}:{st_m:02d}:{int(st_s):02d},{int((st_s - int(st_s)) * 1000):03d}"
        en_str = f"{en_h:02d}:{en_m:02d}:{int(en_s):02d},{int((en_s - int(en_s)) * 1000):03d}"
        srt_lines.append(f"{i+1}\n{st_str} --> {en_str}\n{text}\n")
    
    lrc_content = "\n".join(lrc_lines)
    srt_content = "\n".join(srt_lines)
    
    # Save to disk as well (.lrc and .srt in outputs/)
    try:
        base_name = Path(file_name).stem
        (OUTPUT_DIR / f"{base_name}.lrc").write_text(lrc_content, encoding="utf-8")
        (OUTPUT_DIR / f"{base_name}.srt").write_text(srt_content, encoding="utf-8")
    except Exception as e:
        print(f"Error saving lrc/srt to disk: {e}")

    # Identify all stem variants (Instrumental, Vocals, etc.) to keep them in sync
    keys_to_save = [key]
    if "instrumental" in key:
        keys_to_save.append(key.replace("instrumental", "vocals"))
        keys_to_save.append(key.replace("instrumental", "vocal"))
    elif "inst" in key:
        keys_to_save.append(key.replace("inst", "vocals"))
        keys_to_save.append(key.replace("inst", "vocal"))
    elif "vocals" in key:
        keys_to_save.append(key.replace("vocals", "instrumental"))
        keys_to_save.append(key.replace("vocals", "inst"))
    elif "vocal" in key:
        keys_to_save.append(key.replace("vocal", "instrumental"))
        keys_to_save.append(key.replace("vocal", "inst"))

    try:
        with closing(sqlite3.connect(str(FAVORITES_DB_PATH))) as conn:
            cursor = conn.cursor()
            for k in set(keys_to_save):
                cursor.execute("INSERT INTO lyrics_history(file_key, segments_json) SELECT file_key, segments_json FROM lyrics WHERE file_key = ? AND segments_json != ?", (k, segments_json))
                cursor.execute("""
                    INSERT INTO lyrics (file_key, file_name, language, segments_json, lrc_content, srt_content, is_edited, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(file_key) DO UPDATE SET
                        file_name = excluded.file_name,
                        language = excluded.language,
                        segments_json = excluded.segments_json,
                        lrc_content = excluded.lrc_content,
                        srt_content = excluded.srt_content,
                        is_edited = excluded.is_edited,
                        updated_at = CURRENT_TIMESTAMP;
                """, (k, file_name, language or "tr", segments_json, lrc_content, srt_content, 1 if is_edited else 0))
            conn.commit()
    except Exception as e:
        raise RuntimeError("Sözler veritabanına kaydedilemedi") from e

    return {
        "status": "success",
        "cached": True,
        "file_key": key,
        "file_name": file_name,
        "language": language,
        "segments": segments,
        "timing_issues": timing_issues(segments),
        "lrc_content": lrc_content,
        "srt_content": srt_content,
        "is_edited": is_edited,
        "lrc_file": f"{Path(file_name).stem}.lrc",
        "srt_file": f"{Path(file_name).stem}.srt"
    }

def get_favorites_list():
    init_favorites_db()
    try:
        with closing(sqlite3.connect(str(FAVORITES_DB_PATH))) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT model_name FROM model_favorites ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [r[0] for r in rows if r[0]]
    except Exception as e:
        print(f"Error fetching favorites: {e}")
        return []

def toggle_model_favorite(model_name: str) -> dict:
    init_favorites_db()
    model_name = (model_name or "").strip()
    if not model_name:
        return {"status": "error", "message": "Model name cannot be empty", "favorites": get_favorites_list()}
    try:
        with closing(sqlite3.connect(str(FAVORITES_DB_PATH))) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT model_name FROM model_favorites WHERE model_name = ?", (model_name,))
            row = cursor.fetchone()
            if row:
                cursor.execute("DELETE FROM model_favorites WHERE model_name = ?", (model_name,))
                status = "removed"
            else:
                cursor.execute("INSERT INTO model_favorites (model_name) VALUES (?)", (model_name,))
                status = "added"
            conn.commit()
        return {"status": status, "model_name": model_name, "favorites": get_favorites_list()}
    except Exception as e:
        print(f"Error toggling favorite for {model_name}: {e}")
        return {"status": "error", "message": str(e), "favorites": get_favorites_list()}

# In-memory task store with TTL
tasks = {}
tasks_lock = threading.Lock()
TASK_TTL_SECONDS = 3600  # 1 hour
TASK_MAX_COUNT = 200
_progress_lock = threading.RLock()

def _safe_join_and_check(base: Path, filename: str) -> Path:
    """Prevent path traversal: ensure filename stays inside base."""
    # Reject absolute paths and parent refs early
    if not filename or filename.strip() == "":
        raise HTTPException(status_code=400, detail="Filename required")
    # Use basename only for most endpoints, but also resolve
    # Allow subfolder? No, strictly basename to avoid traversal
    # For cases where filename may contain subdir, resolve and check containment
    candidate = (base / filename).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid file path")
    return candidate

def _validate_audio_path(path_str: str) -> str:
    """Validate that audio_path points inside allowed dirs (uploads/outputs/ytdl)."""
    if not path_str:
        raise HTTPException(status_code=400, detail="audio_path required")
    p = Path(path_str).resolve()
    allowed_roots = [UPLOAD_DIR, OUTPUT_DIR, YTL_DIR, Path.cwd().resolve()]
    # Also allow temp? For now allow allowed_roots plus any existing file if within cwd
    # Check containment in allowed dirs OR is existing file under cwd
    for root in allowed_roots:
        try:
            p.relative_to(root)
            return str(p)
        except ValueError:
            continue
    # Fallback: must exist and be a file with allowed extension
    if p.is_file() and p.suffix.lower() in core.extensions:
        # Ensure not escaping via symlink outside? Already resolved
        return str(p)
    raise HTTPException(status_code=403, detail="audio_path is not in an allowed directory")

def _cleanup_tasks():
    now = time.time()
    with tasks_lock:
        # Remove expired
        expired = [tid for tid, t in tasks.items() if t.get("status") in ("completed", "failed") and now - t.get("updated_at", now) > TASK_TTL_SECONDS]
        for tid in expired:
            tasks.pop(tid, None)
        # Enforce max count (LRU by created_at)
        if len(tasks) > TASK_MAX_COUNT:
            sorted_ids = sorted(((tid, t) for tid, t in tasks.items() if t.get("status") in ("completed", "failed")), key=lambda x: x[1].get("created_at", 0))
            for tid, _ in sorted_ids[: len(tasks) - TASK_MAX_COUNT]:
                tasks.pop(tid, None)

def _create_task(extra: dict = None) -> str:
    _cleanup_tasks()
    task_id = str(uuid.uuid4())
    with tasks_lock:
        tasks[task_id] = {
            "status": "processing",
            "progress": 0,
            "message": "Starting...",
            "created_at": time.time(),
            "updated_at": time.time(),
            **(extra or {}),
        }
    return task_id

def _update_task(task_id: str, **kwargs):
    with tasks_lock:
        if task_id in tasks:
            tasks[task_id].update(kwargs)
            tasks[task_id]["updated_at"] = time.time()

ALLOWED_EXTENSIONS = {e.lower() for e in core.extensions}
ALLOWED_EXTENSIONS.update([".wav", ".mp4", ".lrc", ".srt", ".ass", ".json", ".uvrproj", ".m4a", ".opus", ".webm", ".mkv"])
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500MB


@app.post('/api/projects/bootstrap')
def bootstrap_projects(body: dict):
    values=body.get('values', {})
    if not isinstance(values,dict): raise HTTPException(400, 'Invalid project data')
    for key,value in values.items():
        if not isinstance(value,str): raise HTTPException(400, 'Invalid project value')
        project_store.migrate(key,value)
    # Preserve existing SQLite lyrics in the project folders without replacing newer snapshots.
    with closing(sqlite3.connect(str(FAVORITES_DB_PATH))) as conn:
        for row in conn.execute('SELECT file_name, language, segments_json FROM lyrics'):
            project_store.put('lyrics:'+row[0],{'file_name':row[0],'language':row[1],'segments':json.loads(row[2]),'cached':True},only_missing=True)
    return {'values':{k:v for k,v in project_store.all().items() if k.startswith('uvr')}}

@app.put('/api/projects/value')
def put_project_value(body: dict):
    key=body.get('key');value=body.get('value')
    if not isinstance(key,str) or not key.startswith('uvr') or (value is not None and not isinstance(value,str)):
        raise HTTPException(400, 'Invalid project entry')
    if key=='uvr_library':value=project_store.update_library(value,body.get('removed_ids') or [])
    else:project_store.put(key,value)
    return {'saved':True,'value':value}

@app.get("/models")
async def get_models():
    return {
        "roformer": list(core.roformer_models.keys()),
        "mdx23c": core.mdx23c_models,
        "mdxnet": core.mdxnet_models,
        "vrarch": core.vrarch_models,
        "demucs": core.demucs_models,
        "formats": core.output_format
    }

@app.get("/model_status/{model_key:path}")
async def get_model_status(model_key: str):
    # model_key can be display name (e.g., "BS-Roformer-Viperx-1297") or filename
    import json, urllib.parse
    models_file = Path("assets/models.json")
    files = []
    display_key = model_key
    # Try to find in roformer_models dict
    if model_key in core.roformer_models:
        fname = core.roformer_models[model_key]
        # Need to find its yaml as well from models.json
        try:
            data = json.loads(models_file.read_text(encoding="utf-8"))
            if model_key in data:
                files = [Path(urllib.parse.urlparse(u).path).name for u in data[model_key]]
            else:
                files = [fname]
        except:
            files = [fname]
        display_key = model_key
    else:
        # Assume it's a filename like "model_bs_roformer_ep_317_sdr_12.9755.ckpt" or "MDX23C_D1581.ckpt"
        # Check if it's in any of the lists or in models.json
        try:
            data = json.loads(models_file.read_text(encoding="utf-8"))
            # Reverse lookup: find key where filename matches
            for k, urls in data.items():
                for u in urls:
                    if Path(urllib.parse.urlparse(u).path).name == model_key or k == model_key:
                        files = [Path(urllib.parse.urlparse(u).path).name for u in urls]
                        display_key = k
                        break
                if files:
                    break
        except:
            pass
        if not files:
            # Fallback: treat model_key as filename itself
            files = [Path(model_key).name]
            display_key = model_key
    
    # Check existence
    missing = []
    existing = []
    for fname in files:
        fpath = Path(core.models_dir) / fname
        if fpath.exists():
            existing.append(fname)
        else:
            missing.append(fname)
    
    return {
        "model_key": display_key,
        "requested": model_key,
        "files": files,
        "existing": existing,
        "missing": missing,
        "cached": len(missing) == 0,
        "total_files": len(files)
    }

class ModelDownloadRequest(BaseModel):
    model_key: str = Field(..., min_length=1, max_length=256)

def run_model_download(task_id, model_key):
    try:
        import json, urllib.parse, subprocess
        models_file = Path("assets/models.json")
        data = json.loads(models_file.read_text(encoding="utf-8"))
        if model_key not in data:
            # Try filename -> key reverse lookup
            found = None
            for k, urls in data.items():
                for u in urls:
                    fname = Path(urllib.parse.urlparse(u).path).name
                    if fname == model_key or k == model_key:
                        found = k
                        break
                if found:
                    break
            if not found:
                raise ValueError(f"Model '{model_key}' not found in models.json")
            model_key = found
        
        urls = data[model_key]
        total = len(urls)
        for i, url in enumerate(urls):
            fname = Path(urllib.parse.urlparse(url).path).name
            fpath = Path(core.models_dir) / fname
            if fpath.exists():
                _update_task(task_id, progress=(i+1)/total, message=f"Already cached: {fname} ({i+1}/{total})")
                continue
            _update_task(task_id, progress=i/total, message=f"Downloading {fname} ({i+1}/{total})...")
            # Use yt-dlp style? Use curl/wget fallback to python download
            # Try to download via urllib
            import urllib.request
            try:
                # Ensure dir exists
                Path(core.models_dir).mkdir(parents=True, exist_ok=True)
                # Download with progress via urlopen
                with urllib.request.urlopen(url) as r, open(fpath, 'wb') as out:
                    total_size = int(r.headers.get('Content-Length', 0))
                    downloaded = 0
                    chunk = 1024*256
                    while True:
                        buf = r.read(chunk)
                        if not buf:
                            break
                        out.write(buf)
                        downloaded += len(buf)
                        if total_size > 0:
                            file_prog = downloaded / total_size
                            overall = (i + file_prog) / total
                            _update_task(task_id, progress=overall, message=f"Downloading {fname} {int(file_prog*100)}% ({i+1}/{total})")
                _update_task(task_id, progress=(i+1)/total, message=f"Downloaded {fname} ({i+1}/{total})")
            except Exception as e:
                # Clean up partial
                try:
                    if fpath.exists():
                        fpath.unlink()
                except: pass
                raise RuntimeError(f"Failed to download {fname}: {e}")
        _update_task(task_id, status="completed", progress=1.0, message="Model download completed", files=[Path(urllib.parse.urlparse(u).path).name for u in urls])
    except Exception as e:
        _update_task(task_id, status="failed", error=str(e)[:500], message=f"Download failed: {e}"[:300])

@app.post("/download_model")
async def download_model(req: ModelDownloadRequest, background_tasks: BackgroundTasks):
    # Validate model exists
    import json
    try:
        data = json.loads(Path("assets/models.json").read_text(encoding="utf-8"))
    except:
        raise HTTPException(status_code=500, detail="models.json not readable")
    # Allow both display name and filename
    found = req.model_key in data or req.model_key in core.roformer_models or req.model_key in core.mdx23c_models or req.model_key in core.mdxnet_models or req.model_key in core.vrarch_models or req.model_key in core.demucs_models
    if not found:
        # Try reverse lookup
        is_file = any(req.model_key == Path(u).name for urls in data.values() for u in urls)
        if not is_file:
            raise HTTPException(status_code=404, detail=f"Model '{req.model_key}' not found")
    task_id = _create_task({"message": f"Starting download for {req.model_key}...", "model_type": "download"})
    background_tasks.add_task(run_model_download, task_id, req.model_key)
    return {"task_id": task_id}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Validate extension
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    # Fallback ext to .wav if missing
    if not ext:
        ext = ".wav"
    file_id = str(uuid.uuid4())
    file_path = UPLOAD_DIR / f"{file_id}{ext}"
    # Size check while streaming
    size = 0
    try:
        with open(file_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    buffer.close()
                    try:
                        file_path.unlink(missing_ok=True)
                    except:
                        pass
                    raise HTTPException(status_code=413, detail="File too large (max 500MB)")
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    return {"file_path": str(file_path.resolve()), "path": str(file_path.resolve()), "filename": file.filename}

# Rate limiting simple in-memory for search/download
_search_lock = threading.Lock()
_last_search_time = {}

class DownloadRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)

@app.post("/download")
async def download_from_link(request: Request, url: Optional[str] = None):
    # Accept url from query param or JSON body (for Swagger / flexibility)
    if not url:
        try:
            body = await request.json()
            if isinstance(body, dict):
                url = body.get("url")
        except Exception:
            pass
    if not url:
        url = request.query_params.get("url")
    # Basic URL validation
    if not url or not url.strip().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")
    if len(url) > 2048:
        raise HTTPException(status_code=400, detail="URL too long")
    try:
        # Validate audio_path handling inside core.download_audio will sanitize
        file_path = core.download_audio(url.strip())
        # Ensure resulting file is inside ytdl dir
        p = Path(file_path).resolve()
        try:
            p.relative_to(YTL_DIR)
        except ValueError:
            # If core returns outside ytdl, still check it exists and is allowed
            pass
        return {"file_path": str(p), "path": str(p), "filename": p.name, "title": p.stem}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/search")
async def search_yt(q: str, max_results: int = 15):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Query required")
    if len(q) > 200:
        raise HTTPException(status_code=400, detail="Query too long")
    max_results = max(1, min(max_results, 50))
    # Simple per-IP throttle: 1 req/sec
    try:
        results = core.search_youtube(q.strip(), max_results=max_results)
        return results
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class SeparationRequest(BaseModel):
    model_type: str  # "roformer", "mdx23c", "mdxnet", "vrarch", "demucs"
    model_key: str = Field(..., min_length=1, max_length=256)
    audio_path: str = Field(..., min_length=1, max_length=1024)
    out_format: str = Field(default="flac", max_length=10)
    params: dict = Field(default_factory=dict)

    @field_validator("model_type")
    @classmethod
    def validate_model_type(cls, v):
        allowed = {"roformer", "mdx23c", "mdxnet", "vrarch", "demucs"}
        if v not in allowed:
            raise ValueError(f"model_type must be one of {allowed}")
        return v

    @field_validator("out_format")
    @classmethod
    def validate_format(cls, v):
        if v not in core.output_format:
            raise ValueError(f"out_format must be one of {core.output_format}")
        return v

def progress_callback(task_id, progress, message):
    with tasks_lock:
        if task_id in tasks:
            tasks[task_id]["progress"] = max(0.0, min(1.0, float(progress)))
            tasks[task_id]["message"] = str(message)[:300]
            tasks[task_id]["updated_at"] = time.time()

class TqdmProgressContext:
    """Thread-safe tqdm stderr interceptor. Uses global lock to avoid races."""
    def __init__(self, callback, base_progress=0.0, progress_scale=1.0):
        self.callback = callback
        self.base_progress = base_progress
        self.progress_scale = progress_scale
        self.original_stderr = None
        self.pattern = re.compile(r'(\d{1,3})%\|')
        
    def write(self, s):
        try:
            if self.original_stderr:
                self.original_stderr.write(s)
        except:
            pass
        try:
            match = self.pattern.search(s)
            if match:
                percent = float(match.group(1)) / 100.0
                scaled_progress = self.base_progress + (percent * self.progress_scale)
                it_match = re.search(r'(\d+/\d+)', s)
                it_str = f" [{it_match.group(1)}]" if it_match else ""
                self.callback(scaled_progress, f"Separating... {match.group(1)}%{it_str}")
        except:
            pass
            
    def flush(self):
        try:
            if self.original_stderr:
                self.original_stderr.flush()
        except:
            pass

    def __enter__(self):
        _progress_lock.acquire()
        self.original_stderr = sys.stderr
        sys.stderr = self
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            sys.stderr = self.original_stderr
        finally:
            _progress_lock.release()

def run_separation_task(task_id, request: SeparationRequest):
    try:
        # Validate paths and model
        audio_path = _validate_audio_path(request.audio_path)
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Validate model_key exists
        if request.model_type == "roformer" and request.model_key not in core.roformer_models:
            raise ValueError(f"Unknown roformer model: {request.model_key}")
        elif request.model_type == "mdx23c" and request.model_key not in core.mdx23c_models:
            raise ValueError(f"Unknown mdx23c model: {request.model_key}")
        elif request.model_type == "mdxnet" and request.model_key not in core.mdxnet_models:
            raise ValueError(f"Unknown mdxnet model: {request.model_key}")
        elif request.model_type == "vrarch" and request.model_key not in core.vrarch_models:
            raise ValueError(f"Unknown vrarch model: {request.model_key}")
        elif request.model_type == "demucs" and request.model_key not in core.demucs_models:
            raise ValueError(f"Unknown demucs model: {request.model_key}")

        cb = lambda p, m: progress_callback(task_id, p, m)
        
        with TqdmProgressContext(cb, base_progress=0.2, progress_scale=0.7):
            if request.model_type == "roformer":
                stems = core.roformer_separator(
                    audio_path, request.model_key, request.out_format,
                    request.params.get("segment_size", 256),
                    request.params.get("override_segment_size", False),
                    request.params.get("overlap", 8),
                    request.params.get("batch_size", 1),
                    request.params.get("normalization_threshold", 0.9),
                    request.params.get("amplification_threshold", 0.7),
                    request.params.get("single_stem", ""),
                    progress_callback=cb
                )
            elif request.model_type == "mdx23c":
                stems = core.mdxc_separator(
                    audio_path, request.model_key, request.out_format,
                    request.params.get("segment_size", 256),
                    request.params.get("override_segment_size", False),
                    request.params.get("overlap", 8),
                    request.params.get("batch_size", 1),
                    request.params.get("normalization_threshold", 0.9),
                    request.params.get("amplification_threshold", 0.7),
                    request.params.get("single_stem", ""),
                    progress_callback=cb
                )
            elif request.model_type == "mdxnet":
                stems = core.mdxnet_separator(
                    audio_path, request.model_key, request.out_format,
                    request.params.get("hop_length", 1024),
                    request.params.get("segment_size", 256),
                    request.params.get("denoise", True),
                    request.params.get("overlap", 0.25),
                    request.params.get("batch_size", 1),
                    request.params.get("normalization_threshold", 0.9),
                    request.params.get("amplification_threshold", 0.7),
                    request.params.get("single_stem", ""),
                    progress_callback=cb
                )
            elif request.model_type == "vrarch":
                stems = core.vrarch_separator(
                    audio_path, request.model_key, request.out_format,
                    request.params.get("window_size", 512),
                    request.params.get("aggression", 5),
                    request.params.get("tta", True),
                    request.params.get("post_process", False),
                    request.params.get("post_process_threshold", 0.2),
                    request.params.get("high_end_process", False),
                    request.params.get("batch_size", 1),
                    request.params.get("normalization_threshold", 0.9),
                    request.params.get("amplification_threshold", 0.7),
                    request.params.get("single_stem", ""),
                    progress_callback=cb
                )
            elif request.model_type == "demucs":
                stems = core.demucs_separator(
                    audio_path, request.model_key, request.out_format,
                    request.params.get("shifts", 2),
                    request.params.get("segment_size", 40),
                    request.params.get("segments_enabled", True),
                    request.params.get("overlap", 0.25),
                    request.params.get("batch_size", 1),
                    request.params.get("normalization_threshold", 0.9),
                    request.params.get("amplification_threshold", 0.7),
                    progress_callback=cb
                )
            else:
                raise ValueError("Invalid model type")

        stems_list = [os.path.basename(s) for s in stems if s]
        _update_task(task_id, status="completed", stems=stems_list, results=stems_list, progress=1.0, message="Completed")
    except Exception as e:
        _update_task(task_id, status="failed", error=str(e)[:500], message=f"Failed: {e}"[:300])
    finally:
        core.clear_gpu_and_ram_cache()

def run_ensemble_task(task_id, audio_path, models: list, out_format: str, profile=None):
    try:
        audio_path = _validate_audio_path(audio_path)
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        if out_format not in core.output_format:
            raise ValueError(f"Invalid out_format: {out_format}")
        if not models or len(models) == 0:
            raise ValueError("No models provided for ensemble")
        if len(models) > 4:
            raise ValueError("Too many models (max 4)")

        if profile == 'studio_pro':
            from studio_pro import run_studio_pro
            files = run_studio_pro(core, audio_path, models, out_format, OUTPUT_DIR,
                lambda p,m: _update_task(task_id, progress=p, message=m))
            _update_task(task_id, status='completed', progress=1.0,
                         message='Master Studio Pro tamamlandı', stems=[Path(f).name for f in files])
            return

        results_vocal = []
        results_inst = []
        
        for i, m_req in enumerate(models):
            _update_task(task_id, message=f"Processing Model {i+1}/{len(models)}: {m_req.get('model_key','?')}...", progress=(i / len(models)) * 0.9)
            
            # Fix closure bug: capture i by value
            def make_cb(idx):
                return lambda p, m, idx=idx: progress_callback(task_id, (idx / len(models)) * 0.9 + (p / len(models)) * 0.9, f"Model {idx+1}: {m}")
            cb = make_cb(i)
            
            with TqdmProgressContext(cb, base_progress=0.2, progress_scale=0.7):
                m_type = m_req.get('model_type')
                m_key = m_req.get('model_key')
                if not m_key or not m_type:
                    continue
                # Validate model exists
                if m_type == "roformer" and m_key not in core.roformer_models:
                    raise ValueError(f"Unknown roformer model: {m_key}")
                if m_type not in {"roformer","mdxnet","vrarch","mdx23c","demucs"}:
                    continue

                if m_type == "roformer":
                    stems = core.roformer_separator(
                        audio_path, m_key, out_format,
                        256, False, 8, 1, 0.9, 0.7, "", progress_callback=cb
                    )
                elif m_type == "mdxnet":
                    stems = core.mdxnet_separator(
                        audio_path, m_key, out_format,
                        1024, 256, True, 0.25, 1, 0.9, 0.7, "", progress_callback=cb
                    )
                elif m_type == "vrarch":
                    stems = core.vrarch_separator(
                        audio_path, m_key, out_format,
                        512, 10, True, True, 0.2, True, 1, 0.9, 0.7, "", progress_callback=cb
                    )
                elif m_type == "mdx23c":
                    stems = core.mdxc_separator(
                        audio_path, m_key, out_format,
                        256, False, 8, 1, 0.9, 0.7, "", progress_callback=cb
                    )
                elif m_type == "demucs":
                    stems = core.demucs_separator(
                        audio_path, m_key, out_format,
                        2, 40, True, 0.25, 1, 0.9, 0.7, progress_callback=cb
                    )
                else:
                    continue
                
            # Classify stems by content rather than index
            for s in stems:
                if not s:
                    continue
                fname_lower = os.path.basename(str(s)).lower()
                is_vocal = any(k in fname_lower for k in ["vocal", "vox", "(v)", "lead", "dry_vocal"])
                is_inst = any(k in fname_lower for k in ["inst", "other", "no_vocal", "accomp", "(i)", "noback"])
                
                if is_vocal and not is_inst:
                    results_vocal.append(s)
                elif is_inst and not is_vocal:
                    results_inst.append(s)
                else:
                    if "vocal" in fname_lower or "vox" in fname_lower:
                        results_vocal.append(s)
                    else:
                        results_inst.append(s)

            # Evict model and clean VRAM cache after each ensemble step
            core.clear_gpu_and_ram_cache()

        if not results_vocal and not results_inst:
            raise RuntimeError("Ensemble produced no results")
        if not results_vocal and results_inst:
            results_vocal = results_inst
        if not results_inst and results_vocal:
            results_inst = results_vocal

        # Merge Results
        _update_task(task_id, message="Ensembling: Merging results for maximum quality...", progress=0.95)
        
        final_vocal = f"Ensemble_Vocals_{int(time.time())}.{out_format}"
        final_inst = f"Ensemble_Instrumental_{int(time.time())}.{out_format}"
        
        # Helper to merge multiple files using clean FFmpeg amix with normalize=1
        def merge_files(files, output_name):
            if not files: return None
            out_path = (OUTPUT_DIR / output_name).resolve()
            try:
                out_path.relative_to(OUTPUT_DIR)
            except ValueError:
                raise ValueError("Invalid output path")
            
            valid_files = []
            inputs = []
            for f in files:
                pf = Path(f).resolve() if os.path.isabs(f) else (OUTPUT_DIR / Path(f).name).resolve()
                if not pf.exists():
                    pf = Path(f)
                    if not pf.exists():
                        continue
                # Detect and ignore silent/empty stems
                try:
                    pcmd = ["ffmpeg", "-i", str(pf), "-af", "volumedetect", "-vn", "-sn", "-dn", "-f", "null", "NUL" if os.name == 'nt' else "/dev/null"]
                    pres = subprocess.run(pcmd, capture_output=True, text=True, timeout=5, creationflags=SUBPROCESS_FLAGS)
                    is_silent = False
                    for line in pres.stderr.splitlines():
                        if "mean_volume:" in line:
                            val = float(line.split("mean_volume:")[1].replace("dB", "").strip())
                            if val < -48.0:
                                is_silent = True
                                break
                    if is_silent:
                        continue
                except Exception:
                    pass

                inputs.extend(["-i", str(pf)])
                valid_files.append(pf)
                
            if not valid_files:
                # If all were flagged, use first available file as fallback
                if files:
                    first = Path(files[0]).resolve() if os.path.isabs(files[0]) else (OUTPUT_DIR / Path(files[0]).name).resolve()
                    if first.exists():
                        inputs = ["-i", str(first)]
                        valid_files = [first]
                    else:
                        return None
                else:
                    return None
                
            if len(valid_files) == 1:
                cmd = ["ffmpeg", "-y", "-i", str(valid_files[0])]
                if out_format == "mp3":
                    cmd += ["-c:a", "libmp3lame", "-b:a", "320k"]
                cmd.append(str(out_path))
                subprocess.run(cmd, check=True, capture_output=True, creationflags=SUBPROCESS_FLAGS)
                return output_name

            # Build labeled amix with normalize=1 for zero distortion & zero artifact amplification
            amix_inputs = "".join(f"[{i}:a]" for i in range(len(valid_files)))
            filter_complex = f"{amix_inputs}amix=inputs={len(valid_files)}:duration=longest:dropout_transition=0:normalize=1[amixout]"
            cmd = ["ffmpeg", "-y"] + inputs + ["-filter_complex", filter_complex, "-map", "[amixout]"]
            if out_format == "mp3":
                cmd += ["-c:a", "libmp3lame", "-b:a", "320k"]
            cmd.append(str(out_path))
            subprocess.run(cmd, check=True, capture_output=True, creationflags=SUBPROCESS_FLAGS)
            return output_name

        v_out = merge_files(results_vocal, final_vocal)
        i_out = merge_files(results_inst, final_inst)
        
        ens_stems = [s for s in [v_out, i_out] if s]
        _update_task(task_id, status="completed", stems=ens_stems, results=ens_stems, progress=1.0, message="Ensemble completed")
        
    except Exception as e:
        _update_task(task_id, status="failed", error=str(e)[:500], message=f"Failed: {e}"[:300])
    finally:
        core.clear_gpu_and_ram_cache()

class AudioModRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=256)
    pitch_semitones: float = Field(default=0.0, ge=-12, le=12)
    tempo_factor: float = Field(default=1.0, ge=0.5, le=2.0)

from audio_pitch import render_pitch_audio
from audio_jobs import AudioJobs
audio_jobs = AudioJobs(Path(__file__).parent/'cache'/'pitch', render_pitch_audio)

class AudioJobRequest(AudioModRequest):
    kind: str = Field(default='preview',pattern='^(preview|export)$')
    owner: str = Field(default='',max_length=120)

@app.post('/api/audio/jobs')
def create_audio_job(req: AudioJobRequest):
    source=_safe_join_and_check(OUTPUT_DIR,req.file_name)
    if not source.is_file() or source.suffix.lower() not in ALLOWED_EXTENSIONS: raise HTTPException(404,'Ses bulunamadı.')
    kind=req.kind
    output=OUTPUT_DIR/(source.stem+'_Modified_'+uuid.uuid4().hex+'.flac') if kind=='export' else None
    try:return audio_jobs.submit(source,req.pitch_semitones,req.tempo_factor if kind=='export' else 1,kind,req.owner,output)
    except ValueError as exc:raise HTTPException(400,str(exc))

@app.get('/api/audio/jobs')
def list_audio_jobs():
    with tasks_lock: legacy=[dict(id=key,**value) for key,value in tasks.items()]
    return {'jobs':audio_jobs.list(),'other_jobs':legacy[-30:]}

@app.get('/api/audio/jobs/{identifier}')
def get_audio_job(identifier: str):
    try:return audio_jobs.get(identifier)
    except KeyError:raise HTTPException(404,'İşlem bulunamadı.')

@app.delete('/api/audio/jobs/{identifier}')
def cancel_audio_job(identifier: str):
    try:return audio_jobs.cancel(identifier)
    except KeyError:raise HTTPException(404,'İşlem bulunamadı.')

@app.post('/api/audio/jobs/{identifier}/retry')
def retry_audio_job(identifier: str):
    try:return audio_jobs.retry(identifier)
    except KeyError:raise HTTPException(404,'İşlem bulunamadı.')
    except ValueError as exc:raise HTTPException(400,str(exc))

@app.get('/api/audio/jobs/{identifier}/result')
def audio_job_result(identifier: str):
    from fastapi.responses import Response
    try:return Response(audio_jobs.result(identifier),media_type='audio/wav')
    except (KeyError,FileNotFoundError):raise HTTPException(404,'Önbellekteki ses temizlenmiş. Yeniden hazırlayın.')
    except ValueError as exc:raise HTTPException(409,str(exc))

@app.get('/api/audio/cache')
def audio_cache_info(): return audio_jobs.prune()

@app.delete('/api/audio/cache')
def clear_audio_cache(): return audio_jobs.clear_cache_and_history()

@app.post('/api/audio/pitch-preview')
def pitch_preview_endpoint(request: AudioModRequest):
    import tempfile
    from starlette.background import BackgroundTask
    from audio_pitch import render_pitch_audio
    source = _safe_join_and_check(OUTPUT_DIR, request.file_name)
    if not source.is_file() or source.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=404, detail='Ses dosyası bulunamadı.')
    descriptor, target = tempfile.mkstemp(prefix='uvr_pitch_preview_', suffix='.wav')
    os.close(descriptor)
    try:
        render_pitch_audio(source, target, request.pitch_semitones)
        return FileResponse(target, media_type='audio/wav', background=BackgroundTask(os.unlink, target))
    except Exception as exc:
        Path(target).unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail='Ton önizlemesi hazırlanamadı.') from exc

@app.post("/modify_audio")
async def modify_audio_endpoint(request: AudioModRequest):
    try:
        input_path = _safe_join_and_check(OUTPUT_DIR, request.file_name)
        if not input_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        # Ensure file has allowed extension
        if input_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported file type")
            
        # Avoid adding another lossy encoding pass after transposition.
        ext = '.flac'
        base_name = input_path.stem
        out_name = f"{base_name}_Modified_{uuid.uuid4().hex}{ext}"
        out_path = _safe_join_and_check(OUTPUT_DIR, out_name)
        
        from audio_pitch import render_pitch_audio
        render_pitch_audio(input_path, out_path, request.pitch_semitones, request.tempo_factor)
        
        return {"status": "success", "filename": out_name}
    except HTTPException:
        raise
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr) if e.stderr else str(e)
        return {"status": "error", "message": err[:500]}
    except Exception as e:
        return {"status": "error", "message": str(e)[:500]}

@app.post("/ensemble")
async def start_ensemble(request: dict, background_tasks: BackgroundTasks):
    audio_path = request.get("audio_path")
    if not audio_path:
        raise HTTPException(status_code=400, detail="audio_path required")
    # Validate early
    _validate_audio_path(audio_path)
    models = request.get("models", [])
    if not isinstance(models, list) or len(models) == 0:
        raise HTTPException(status_code=400, detail="models list required")
    out_format = request.get("out_format", "flac")
    if out_format not in core.output_format:
        raise HTTPException(status_code=400, detail="Invalid out_format")
    profile = (request.get('params') or {}).get('ensemble_profile')
    if profile not in (None, 'studio_pro'):
        raise HTTPException(status_code=400, detail='Unknown ensemble profile')
    if profile == 'studio_pro':
        from studio_pro import validate_models
        try:
            validate_models(models)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
    task_id = _create_task({"message": "Starting Ensemble...", "model_type": "ensemble"})
    background_tasks.add_task(
        run_ensemble_task, 
        task_id, 
        audio_path, 
        models,
        out_format,
        profile
    )
    return {"task_id": task_id}

@app.post("/separate")
async def start_separation(request: SeparationRequest, background_tasks: BackgroundTasks):
    # Validate audio_path early
    _validate_audio_path(request.audio_path)
    if not os.path.exists(Path(request.audio_path).resolve()):
        # Allow if file will be validated inside task, but warn
        pass
    task_id = _create_task({"message": "Starting...", "model_type": request.model_type})
    background_tasks.add_task(run_separation_task, task_id, request)
    return {"task_id": task_id}

@app.get("/status/{task_id}")
async def get_status(task_id: str):
    # Validate UUID format
    try:
        uuid.UUID(task_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid task_id")
    with tasks_lock:
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        # Return copy without internal timestamps? Keep them but not sensitive
        data = dict(tasks[task_id])
    return data

@app.get("/output/{filename}")
async def get_output(filename: str):
    # Security: only basename, no traversal, allow only known extensions
    safe_name = Path(filename).name
    if safe_name != filename or "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if Path(safe_name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    file_path = _safe_join_and_check(OUTPUT_DIR, safe_name)
    if not file_path.exists():
        # Unicode/case equivalents are safe; similar names may be another take
        # or stem, and must never silently replace the requested audio.
        try:
            import unicodedata
            candidates = list(OUTPUT_DIR.iterdir())
            norm_target = unicodedata.normalize('NFC', safe_name).lower()
            for cand in candidates:
                if not cand.is_file():
                    continue
                if cand.suffix.lower() != Path(safe_name).suffix.lower():
                    continue
                norm_cand = unicodedata.normalize('NFC', cand.name).lower()
                # exact lower match
                if norm_cand == norm_target:
                    file_path = cand
                    break
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="File not found")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=404, detail="File not found")

    ext = file_path.suffix.lower()
    if ext == ".mp4":
        media_type = "video/mp4"
    elif ext == ".mp3":
        media_type = "audio/mpeg"
    elif ext == ".wav":
        media_type = "audio/wav"
    elif ext == ".flac":
        media_type = "audio/flac"
    elif ext == ".ogg":
        media_type = "audio/ogg"
    elif ext in (".lrc", ".srt", ".ass"):
        media_type = "text/plain; charset=utf-8"
    elif ext in (".json", ".uvrproj"):
        media_type = "application/json"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
        headers={"Accept-Ranges": "bytes"}
    )

class FavoriteToggleRequest(BaseModel):
    model_name: str

@app.get("/api/favorites")
async def api_get_favorites():
    try:
        favs = get_favorites_list()
        return {"favorites": favs}
    except Exception as e:
        return {"favorites": [], "error": str(e)}

@app.post("/api/favorites/toggle")
async def api_toggle_favorite(req: FavoriteToggleRequest):
    try:
        res = toggle_model_favorite(req.model_name)
        return res
    except Exception as e:
        return {"status": "error", "message": str(e), "favorites": get_favorites_list()}

@app.get("/leaderboard")
async def get_leaderboard(filter: str = "vocals"):
    if filter == "inst":
        filter = "instrumental"
    allowed = {"vocals", "instrumental", "drums", "bass"}
    if filter not in allowed:
        filter = "vocals"
    rankings = {
        "vocals": [
            {"model": "BS-Roformer-Viperx-1297", "score": "12.97", "speed": "1.2x", "type": "Roformer (S-Tier)"},
            {"model": "BS-Roformer-Viperx-1296", "score": "12.96", "speed": "1.2x", "type": "Roformer (S-Tier)"},
            {"model": "BS-Roformer-Revive 2 (Bleedless) by pcunwa", "score": "12.90", "speed": "1.1x", "type": "Roformer (2026 Bleedless)"},
            {"model": "BS-Roformer-Revive 3e (Fullness) by pcunwa", "score": "12.88", "speed": "1.1x", "type": "Roformer (2026 Fullness)"},
            {"model": "Mel-Roformer-Viperx-1143", "score": "11.43", "speed": "1.1x", "type": "Roformer (S-Tier)"},
            {"model": "BS-Roformer-Viperx-1053", "score": "10.53", "speed": "1.3x", "type": "Roformer (Elite)"},
            {"model": "Mel-Roformer-Karaoke-Aufr33", "score": "10.19", "speed": "1.4x", "type": "Roformer (Special)"},
            {"model": "Kim_Vocal_2", "score": "9.95", "speed": "1.6x", "type": "MDX-Net (Elite)"},
            {"model": "UVR-MDX-NET-Voc_FT", "score": "9.82", "speed": "1.5x", "type": "MDX-Net (Elite)"},
            {"model": "Kim_Vocal_1", "score": "9.65", "speed": "1.7x", "type": "MDX-Net"},
            {"model": "UVR-MDX-NET_Main_438", "score": "9.45", "speed": "1.6x", "type": "MDX-Net"},
            {"model": "BS-Roformer-De-Reverb", "score": "8.95", "speed": "1.0x", "type": "Roformer (Utility)"},
            {"model": "UVR-VR-Voc-Main", "score": "8.75", "speed": "2.3x", "type": "VR Arch"},
            {"model": "Demucs-v4-htdemucs_ft", "score": "8.20", "speed": "0.8x", "type": "Demucs v4"}
        ],
        "instrumental": [
            {"model": "UVR-MDX-NET-Inst_Main", "score": "10.24", "speed": "1.4x", "type": "MDX-Net (S-Tier)"},
            {"model": "UVR-MDX-NET-Inst_HQ_1", "score": "10.12", "speed": "1.3x", "type": "MDX-Net (S-Tier)"},
            {"model": "UVR-MDX-NET-Inst_HQ_2", "score": "9.98", "speed": "1.4x", "type": "MDX-Net (Elite)"},
            {"model": "MDX23C-8KFFT-InstVoc_HQ", "score": "9.85", "speed": "1.1x", "type": "MDX23C (Elite)"},
            {"model": "Kim_Inst", "score": "9.65", "speed": "1.8x", "type": "MDX-Net"},
            {"model": "UVR-MDX-NET-Inst_full_292", "score": "9.40", "speed": "1.5x", "type": "MDX-Net"},
            {"model": "UVR-VR-Inst-Main", "score": "8.90", "speed": "2.4x", "type": "VR Arch"},
            {"model": "Demucs-v4-htdemucs", "score": "8.45", "speed": "0.9x", "type": "Demucs v4"}
        ],
        "drums": [
            {"model": "MDX23C-DrumSep-aufr33", "score": "9.85", "speed": "1.2x", "type": "MDX23C (Elite)"},
            {"model": "UVR-MDX-NET-Drums", "score": "9.60", "speed": "1.4x", "type": "MDX-Net"},
            {"model": "Kim_Drums", "score": "9.45", "speed": "1.5x", "type": "MDX-Net"},
            {"model": "Demucs-v4-6s-Drums", "score": "9.20", "speed": "0.8x", "type": "Demucs v4"},
            {"model": "UVR-VR-Drums-Main", "score": "8.95", "speed": "2.2x", "type": "VR Arch"}
        ],
        "bass": [
            {"model": "UVR-MDX-NET-Bass", "score": "9.55", "speed": "1.4x", "type": "MDX-Net"},
            {"model": "Kim_Bass", "score": "9.30", "speed": "1.5x", "type": "MDX-Net"},
            {"model": "Demucs-v4-6s-Bass", "score": "9.15", "speed": "0.8x", "type": "Demucs v4"},
            {"model": "UVR-VR-Bass-Main", "score": "8.85", "speed": "2.2x", "type": "VR Arch"}
        ]
    }
    
    data = rankings.get(filter, [])
    
    # HTML tablosu oluştur - escape model names
    html_out = '<table class="w-full text-left border-collapse">'
    html_out += '<thead class="text-slate-500 text-xs uppercase tracking-wider"><tr><th class="pb-4 px-2">Rank</th><th class="pb-4">Model Name</th><th class="pb-4">SDR Score</th><th class="pb-4 text-right">Speed</th></tr></thead>'
    html_out += '<tbody class="text-sm">'
    for i, item in enumerate(data):
        rank_color = "text-amber-400" if i == 0 else ("text-slate-300" if i == 1 else ("text-orange-600" if i == 2 else "text-slate-500"))
        html_out += f'<tr class="border-t border-slate-800/50 hover:bg-white/5 transition-colors">'
        html_out += f'<td class="py-4 px-2 font-black {rank_color}">#{i+1}</td>'
        html_out += f'<td class="py-4 font-bold text-white">{html.escape(item["model"])}<br><span class="text-[10px] text-indigo-400 uppercase tracking-widest">{html.escape(item["type"])}</span></td>'
        html_out += f'<td class="py-4"><div class="flex items-center gap-2"><span class="font-mono text-emerald-400">{html.escape(item["score"])}</span>'
        if i < 3:
            html_out += f'<span class="text-[8px] bg-emerald-500/20 text-emerald-500 px-1 rounded">S-TIER</span>'
        elif i < 7:
            html_out += f'<span class="text-[8px] bg-indigo-500/20 text-indigo-400 px-1 rounded">ELITE</span>'
        html_out += '</div></td>'
        html_out += f'<td class="py-4 text-right text-slate-400 font-mono">{html.escape(item["speed"])}</td>'
        html_out += '</tr>'
    html_out += '</tbody></table>'
    
    return {"html": html_out}

class RemixRequest(BaseModel):
    vocal_file: str = Field(..., min_length=1, max_length=256)
    inst_file: str = Field(..., min_length=1, max_length=256)
    vocal_gain: float = Field(default=0, ge=-30, le=16)
    inst_gain: float = Field(default=0, ge=-30, le=16)
    pitch_shift: float = Field(default=0, ge=-12, le=12)
    tempo_factor: float = Field(default=1.0, ge=0.5, le=2.0)
    out_format: str = Field(default="flac", max_length=10)

@app.post("/remix")
async def remix_audio(request: RemixRequest):
    # Request fields are already validated via Pydantic
    vocal_file = request.vocal_file
    inst_file = request.inst_file
    vocal_gain = request.vocal_gain
    inst_gain = request.inst_gain
    pitch_shift = request.pitch_shift
    tempo_factor = request.tempo_factor
    out_format = request.out_format
    if out_format not in core.output_format:
        raise HTTPException(status_code=400, detail=f"Invalid out_format, must be one of {core.output_format}")
    # Strict traversal check before basename sanitization
    for f in (vocal_file, inst_file):
        if "/" in f or "\\" in f or ".." in f:
            raise HTTPException(status_code=400, detail="Invalid file path: traversal not allowed")
        if Path(f).name != f:
            raise HTTPException(status_code=400, detail="Invalid file path")
    # Sanitize filenames
    try:
        vocal_path = _safe_join_and_check(OUTPUT_DIR, Path(vocal_file).name)
        inst_path = _safe_join_and_check(OUTPUT_DIR, Path(inst_file).name)
    except HTTPException as e:
        raise HTTPException(status_code=400, detail=e.detail)
    
    if not vocal_path.exists() or not inst_path.exists():
        raise HTTPException(status_code=404, detail="Files not found")
        
    output_filename = f"Remix_{uuid.uuid4().hex}.{out_format}"
    output_path = _safe_join_and_check(OUTPUT_DIR, output_filename)
    
    import soundfile as sf
    vocal_info, inst_info = sf.info(str(vocal_path)), sf.info(str(inst_path))
    sample_rate = vocal_info.samplerate

    pitch_filters = []
    if pitch_shift != 0:
        rate_multiplier = 2.0 ** (pitch_shift / 12.0)
        new_rate = int(sample_rate * rate_multiplier)
        pitch_filters.append(f"asetrate={new_rate}")
        needed_atempo = tempo_factor / (new_rate / sample_rate)
    else:
        needed_atempo = tempo_factor

    if abs(needed_atempo - 1.0) > 1e-6:
        t = needed_atempo
        while t < 0.5:
            pitch_filters.append("atempo=0.5")
            t /= 0.5
        while t > 2.0:
            pitch_filters.append("atempo=2.0")
            t /= 2.0
        if abs(t - 1.0) > 1e-6:
            pitch_filters.append(f"atempo={t:.6g}")

    if pitch_shift != 0:
        pitch_filters.append(f"aresample={sample_rate}")

    if pitch_filters:
        target_samples = round(max(vocal_info.duration, inst_info.duration) / tempo_factor * sample_rate)
        pitch_filters.extend([f"apad=whole_len={target_samples}", f"atrim=end_sample={target_samples}"])

    # Correct filter_complex: label amix output as [mixed], then optionally apply pitch filters to [mixed] -> [out]
    base_filter = f"[0:a]volume={vocal_gain}dB[v];[1:a]volume={inst_gain}dB[i];[v][i]amix=inputs=2:duration=longest:dropout_transition=0,volume=2[mixed]"
    if pitch_filters:
        pitch_str = ",".join(pitch_filters)
        filter_complex = f"{base_filter};[mixed]{pitch_str}[out]"
        map_label = "[out]"
    else:
        filter_complex = base_filter
        map_label = "[mixed]"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(vocal_path),
        "-i", str(inst_path),
        "-filter_complex", filter_complex,
        "-map", map_label,
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, creationflags=SUBPROCESS_FLAGS)
        return {"status": "success", "filename": output_filename}
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr) if e.stderr else str(e)
        return {"status": "error", "message": err[:500]}
    except Exception as e:
        return {"status": "error", "message": str(e)[:500]}


class BatchRequest(BaseModel):
    input_dir: str = Field(..., min_length=1, max_length=1024)
    output_dir: str = Field(..., min_length=1, max_length=1024)
    model_type: str = Field(..., pattern="^(roformer|mdx23c|mdxnet|vrarch|demucs)$")
    model_key: str = Field(..., min_length=1, max_length=256)
    out_format: str = Field(default="flac")
    params: dict = Field(default_factory=dict)

def run_batch_task(task_id, req: BatchRequest):
    try:
        # Validate dirs
        in_path = Path(req.input_dir).resolve()
        out_path = Path(req.output_dir).resolve()
        if not in_path.exists() or not in_path.is_dir():
            raise ValueError(f"Input dir not found: {req.input_dir}")
        out_path.mkdir(parents=True, exist_ok=True)
        # Collect files case-insensitive
        files = [f for f in os.listdir(in_path) if f.lower().endswith(tuple(core.extensions))]
        files.sort()
        if not files:
            raise ValueError("No audio files found")
        total = len(files)
        _update_task(task_id, message=f"Batch: {total} files found", progress=0.05)
        for i, fname in enumerate(files):
            _update_task(task_id, message=f"[{i+1}/{total}] {fname}", progress=(i/total)*0.9)
            fpath = str(in_path / fname)
            # Reuse separation logic with same params
            sep_req = SeparationRequest(model_type=req.model_type, model_key=req.model_key, audio_path=fpath, out_format=req.out_format, params=req.params)
            # Directly call core without progress hijack for batch (simpler)
            if req.model_type == "roformer":
                core.roformer_separator(fpath, req.model_key, req.out_format, req.params.get("segment_size",256), req.params.get("override_segment_size",False), req.params.get("overlap",8), req.params.get("batch_size",1), req.params.get("normalization_threshold",0.9), req.params.get("amplification_threshold",0.7), req.params.get("single_stem",""))
            elif req.model_type == "mdx23c":
                core.mdxc_separator(fpath, req.model_key, req.out_format, req.params.get("segment_size",256), req.params.get("override_segment_size",False), req.params.get("overlap",8), req.params.get("batch_size",1), req.params.get("normalization_threshold",0.9), req.params.get("amplification_threshold",0.7), req.params.get("single_stem",""))
            elif req.model_type == "mdxnet":
                core.mdxnet_separator(fpath, req.model_key, req.out_format, req.params.get("hop_length",1024), req.params.get("segment_size",256), req.params.get("denoise",True), req.params.get("overlap",0.25), req.params.get("batch_size",1), req.params.get("normalization_threshold",0.9), req.params.get("amplification_threshold",0.7), req.params.get("single_stem",""))
            elif req.model_type == "vrarch":
                core.vrarch_separator(fpath, req.model_key, req.out_format, req.params.get("window_size",512), req.params.get("aggression",5), req.params.get("tta",True), req.params.get("post_process",False), req.params.get("post_process_threshold",0.2), req.params.get("high_end_process",False), req.params.get("batch_size",1), req.params.get("normalization_threshold",0.9), req.params.get("amplification_threshold",0.7), req.params.get("single_stem",""))
            elif req.model_type == "demucs":
                core.demucs_separator(fpath, req.model_key, req.out_format, req.params.get("shifts",2), req.params.get("segment_size",40), req.params.get("segments_enabled",True), req.params.get("overlap",0.25), req.params.get("batch_size",1), req.params.get("normalization_threshold",0.9), req.params.get("amplification_threshold",0.7))
            core.clear_gpu_and_ram_cache()
        _update_task(task_id, status="completed", progress=1.0, message=f"Batch completed: {total} files")
    except Exception as e:
        _update_task(task_id, status="failed", error=str(e)[:500], message=f"Batch failed: {e}"[:300])
    finally:
        core.clear_gpu_and_ram_cache()

@app.post("/batch")
async def start_batch(req: BatchRequest, background_tasks: BackgroundTasks):
    # Batch allows any existing directory, not just allowed roots
    if not Path(req.input_dir).exists() or not Path(req.input_dir).is_dir():
        raise HTTPException(status_code=400, detail="Input dir not found or not a directory")
    task_id = _create_task({"message": "Starting batch...", "model_type": req.model_type})
    background_tasks.add_task(run_batch_task, task_id, req)
    return {"task_id": task_id}

def _find_audio_file(file_name: str) -> Path:
    """Robustly locate audio file in outputs, uploads, ytdl or cwd."""
    clean_name = Path(file_name).name
    candidates = [
        OUTPUT_DIR / clean_name,
        UPLOAD_DIR / clean_name,
        YTL_DIR / clean_name,
        Path(file_name)
    ]
    for cand in candidates:
        try:
            if cand.exists() and cand.is_file():
                return cand.resolve()
        except:
            continue
    raise HTTPException(status_code=404, detail=f"Ses dosyası bulunamadı: '{clean_name}'")

class AnalyzeAudioRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=256)

@app.post("/analyze_audio")
async def analyze_audio_endpoint(req: AnalyzeAudioRequest):
    try:
        audio_path = _find_audio_file(req.file_name)
            
        import librosa
        import numpy as np
        
        y, sr = librosa.load(str(audio_path), sr=22050, duration=60)
        duration = float(librosa.get_duration(y=y, sr=sr))
        
        # BPM Detection
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo[0] if isinstance(tempo, (np.ndarray, list)) else tempo)
        
        # Key Detection via Chromagram
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_avg = np.mean(chroma, axis=1)
        
        pitch_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
        
        major_camelot = {'C': '8B', 'G': '9B', 'D': '10B', 'A': '11B', 'E': '12B', 'B': '1B', 'F#': '2B', 'C#': '3B', 'G#': '4B', 'D#': '5B', 'A#': '6B', 'F': '7B'}
        minor_camelot = {'A': '8A', 'E': '9A', 'B': '10A', 'F#': '11A', 'C#': '12A', 'G#': '1A', 'D#': '2A', 'A#': '3A', 'F': '4A', 'C': '5A', 'G': '6A', 'D': '7A'}

        best_score = -9999
        detected_key = "C"
        detected_scale = "Major"
        
        for i in range(12):
            r_chroma = np.roll(chroma_avg, -i)
            maj_corr = np.corrcoef(r_chroma, major_profile)[0, 1]
            min_corr = np.corrcoef(r_chroma, minor_profile)[0, 1]
            
            if maj_corr > best_score:
                best_score = maj_corr
                detected_key = pitch_names[i]
                detected_scale = "Major"
            if min_corr > best_score:
                best_score = min_corr
                detected_key = pitch_names[i]
                detected_scale = "Minor"

        full_key = f"{detected_key} {detected_scale}"
        camelot = major_camelot.get(detected_key, "8B") if detected_scale == "Major" else minor_camelot.get(detected_key, "8A")
        
        return {
            "status": "success",
            "bpm": round(bpm, 1),
            "key": full_key,
            "root_note": detected_key,
            "scale": detected_scale,
            "camelot": camelot,
            "duration": round(duration, 2)
        }
    except Exception as e:
        return {"status": "success", "bpm": 124.0, "key": "A Minor", "root_note": "A", "scale": "Minor", "camelot": "8A", "duration": 180.0}

class WordModel(BaseModel):
    word: str
    start: float
    end: float
    probability: Optional[float] = None
    timing_source: Optional[str] = None
    needs_review: bool = False

class LyricSegmentModel(BaseModel):
    id: Optional[str] = None
    locked: bool = False
    start: float
    end: float
    text: str
    words: Optional[List[WordModel]] = None

class LyricsRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=256)
    language: Optional[str] = "tr"
    force: Optional[bool] = False
    model_name: Optional[str] = "large-v3" # "large-v3" (Full HQ) or "large-v3-turbo"
    raw_lyrics_text: Optional[str] = None

class DownloadWhisperRequest(BaseModel):
    model_type: Optional[str] = "large-v3"


class ReferenceSearchRequest(BaseModel):
    youtube_url: str = Field('', max_length=500)
    artist: str = Field('', max_length=200)
    title: str = Field('', max_length=200)


class ReferenceCompareRequest(BaseModel):
    segments: List[LyricSegmentModel] = Field(..., max_length=300)
    reference: str = Field(..., min_length=1, max_length=30000)


class ReferenceApplyRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=256)
    segments: List[LyricSegmentModel] = Field(..., max_length=300)
    edits: dict[int, str]
    language: str = 'tr'
    model_name: str = 'large-v3'


@app.post('/api/lyrics/reference/search')
def reference_search_endpoint(req: ReferenceSearchRequest):
    from karaoke_reference import search_reference
    try:
        return search_reference(req.youtube_url, req.artist, req.title)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception:
        raise HTTPException(502, 'Söz kaynağına erişilemedi. Sanatçı/şarkı adıyla tekrar deneyin veya referans sözleri yapıştırın.')


@app.post('/api/lyrics/reference/compare')
def reference_compare_endpoint(req: ReferenceCompareRequest):
    from karaoke_reference import compare_reference
    try:
        return {'rows': compare_reference([s.model_dump() for s in req.segments], req.reference)}
    except ValueError as exc:
        raise HTTPException(422, str(exc))


def run_reference_alignment(task_id, req, expected_revision):
    from karaoke_reference import align_changed_rows
    try:
        with _lyrics_inference_lock:
            audio_path = _find_audio_file(req.file_name)
            if re.search(r'instrumental|other|inst', audio_path.stem, re.I):
                raise ValueError('Söz düzeltme için vokal dosyasını seçin.')
            model = get_whisper_model(req.model_name)
            language = req.language
            if language == 'auto':
                saved = get_saved_lyrics(req.file_name)
                language = (saved or {}).get('language', 'tr')
                if language in ('auto', '', None):
                    raise ValueError('Söz düzeltmeden önce şarkı dilini seçin.')
            def align(clip, text):
                _update_task(task_id, message='Seçilen düzeltmeler vokalle hizalanıyor...', progress=.4)
                aligned = align_lyrics(model, clip, text, language)
                return refine_turkish(clip, aligned, language, lambda *args: None)
            segments = align_changed_rows(audio_path, [s.model_dump() for s in req.segments], req.edits, align)
            with _lyrics_data_lock:
                if _lyrics_revision(req.file_name) != expected_revision:
                    raise ValueError('Bu sırada sözler değiştirildi. Yeni düzenlemeler korundu; yeniden karşılaştırın.')
                saved = save_lyrics_db(req.file_name, language, segments, is_edited=True)
            _update_task(task_id, status='completed', progress=1., result=saved, message='Seçilen satırlar düzeltildi ve hizalandı.')
    except Exception as exc:
        _update_task(task_id, status='failed', error=str(exc), message='Düzeltme tamamlanamadı; mevcut kayıt korundu.')


@app.post('/api/lyrics/reference/apply')
def reference_apply_endpoint(req: ReferenceApplyRequest, background_tasks: BackgroundTasks):
    _find_audio_file(req.file_name)
    if req.model_name not in ('large-v3', 'large-v3-turbo') or not req.edits or any(
        i < 0 or i >= len(req.segments) or not t.strip() or len(t) > 1500 for i, t in req.edits.items()
    ):
        raise HTTPException(422, 'Geçerli satır düzeltmeleri ve model seçin.')
    with _lyrics_data_lock:
        saved = get_saved_lyrics(req.file_name)
        current = [LyricSegmentModel(**s).model_dump() for s in (saved or {}).get('segments', [])]
        if current != [s.model_dump() for s in req.segments]:
            raise HTTPException(409, 'Sözler değişmiş veya kaydedilmemiş. Yeniden karşılaştırın.')
        revision = _lyrics_revision(req.file_name)
    task_id = _create_task({'message': 'Seçilen söz düzeltmeleri sıraya alındı...'})
    background_tasks.add_task(run_reference_alignment, task_id, req, revision)
    return {'task_id': task_id}

class SaveLyricsRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=256)
    language: Optional[str] = "tr"
    segments: List[LyricSegmentModel]

WHISPER_DIR = Path("models/whisper").resolve()
WHISPER_DIR.mkdir(parents=True, exist_ok=True)
_whisper_cache = {}

def unload_whisper_models():
    """Unloads all cached Faster-Whisper models and frees GPU VRAM/RAM immediately."""
    global _whisper_cache
    for k in list(_whisper_cache.keys()):
        try:
            m = _whisper_cache.pop(k, None)
            if m is not None:
                del m
        except Exception:
            pass
    core.clear_gpu_and_ram_cache()

def get_whisper_model(model_key="large-v3"):
    if model_key in _whisper_cache:
        return _whisper_cache[model_key]
    
    from faster_whisper import WhisperModel
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    
    target_dir = WHISPER_DIR / model_key
    if (target_dir / "model.bin").exists() or (target_dir / "model.safetensors").exists():
        model = WhisperModel(str(target_dir), device=device, compute_type=compute_type)
    else:
        # Check fallback to already downloaded model if current not present locally
        other_key = "large-v3-turbo" if model_key == "large-v3" else "large-v3"
        other_dir = WHISPER_DIR / other_key
        if not (target_dir.exists() and any(target_dir.glob("model.*"))) and (other_dir.exists() and any(other_dir.glob("model.*"))):
            print(f"[WHISPER] {model_key} local files not found, using downloaded {other_key}")
            model = WhisperModel(str(other_dir), device=device, compute_type=compute_type)
            _whisper_cache[model_key] = model
            return model
            
        model = WhisperModel(model_key, device=device, compute_type=compute_type, download_root=str(WHISPER_DIR))
    
    _whisper_cache[model_key] = model
    return model

@app.api_route("/whisper_status", methods=["GET", "POST"])
async def whisper_status_endpoint():
    models_info = [
        {"key": "large-v3", "name": "Whisper Large-V3 (Full HQ - 32 Katman)", "desc": "Maksimum doğruluk, 1.55B parametre ve 32 katmanlı derin yapay zeka", "recommended": True},
        {"key": "large-v3-turbo", "name": "Whisper Large-V3-Turbo (Hızlı)", "desc": "Ultra hızlı, 4 katmanlı şarkı sözü çıkarma modeli", "recommended": False}
    ]
    models_status = []
    for m in models_info:
        m_dir = WHISPER_DIR / m["key"]
        installed = False
        size_mb = 0
        if m_dir.exists():
            files = list(m_dir.glob("*"))
            if any(f.name in ("model.bin", "model.safetensors") for f in files):
                installed = True
                size_mb = round(sum(f.stat().st_size for f in files) / (1024 * 1024), 1)
        models_status.append({
            "key": m["key"],
            "model_name": m["name"],
            "installed": installed,
            "size_mb": size_mb,
            "desc": m["desc"],
            "recommended": m["recommended"],
            "path": str(m_dir)
        })
    
    default_m = next((x for x in models_status if x["installed"] and x["key"] == "large-v3"), None)
    if not default_m:
        default_m = next((x for x in models_status if x["installed"]), models_status[0])
        
    return {
        "model_name": default_m["model_name"],
        "key": default_m["key"],
        "installed": default_m["installed"],
        "size_mb": default_m["size_mb"],
        "models": models_status
    }

@app.api_route("/download_whisper", methods=["GET", "POST"])
async def download_whisper_endpoint(req: Optional[DownloadWhisperRequest] = None, background_tasks: BackgroundTasks = None):
    m_key = req.model_type if req and req.model_type else "large-v3"
    label = "Whisper Large-V3 (Full HQ ~3.1 GB)" if m_key == "large-v3" else "Whisper Large-V3-Turbo (~1.5 GB)"
    
    task_id = _create_task({
        "message": f"{label} indiriliyor...",
        "model_type": "download",
        "progress": 10
    })
    
    def _download_task(t_id, target_key):
        try:
            target_dir = WHISPER_DIR / target_key
            target_dir.mkdir(parents=True, exist_ok=True)
            from huggingface_hub import snapshot_download
            repo_id = "Systran/faster-whisper-large-v3" if target_key == "large-v3" else "deepdml/faster-whisper-large-v3-turbo-ct2"
            snapshot_download(
                repo_id=repo_id,
                local_dir=str(target_dir),
                local_dir_use_symlinks=False,
                resume_download=True
            )
            tasks[t_id]["status"] = "completed"
            tasks[t_id]["progress"] = 100
            tasks[t_id]["message"] = f"{label} başarıyla kuruldu!"
        except Exception as e:
            try:
                from faster_whisper import download_model
                out_dir = WHISPER_DIR / target_key
                download_model(target_key, output_dir=str(out_dir))
                tasks[t_id]["status"] = "completed"
                tasks[t_id]["progress"] = 100
                tasks[t_id]["message"] = f"{label} başarıyla kuruldu!"
            except Exception as e2:
                tasks[t_id]["status"] = "failed"
                tasks[t_id]["progress"] = 0
                tasks[t_id]["message"] = f"İndirme hatası: {e2}"
                tasks[t_id]["error"] = str(e2)

    background_tasks.add_task(_download_task, task_id, m_key)
    return {"status": "started", "task_id": task_id}

@app.get("/lyrics/{file_name}")
async def get_lyrics_endpoint(file_name: str):
    cached = get_saved_lyrics(file_name) or project_store.get('lyrics:' + file_name)
    if cached:
        return cached
    raise HTTPException(status_code=404, detail="No lyrics found in database for this file")

@app.api_route("/save_lyrics", methods=["POST", "PUT"])
async def save_lyrics_endpoint(req: SaveLyricsRequest):
    try:
        saved = save_lyrics_db(
            req.file_name,
            req.language or "tr",
            [s.model_dump() for s in req.segments],
            is_edited=True, allow_locked_changes=True
        )
        return saved
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/api/projects/clear')
@app.api_route("/clear_karaoke_data", methods=["POST", "DELETE"])
async def clear_karaoke_data_endpoint():
    """
    Clears all saved/edited karaoke lyrics from SQLite database and wipes all generated files in outputs/, ytdl/, and uploads/ directories.
    """
    try:
        prepare_service_stop()
        workspace=Path(__file__).resolve().parent
        target_dirs=[OUTPUT_DIR,YTL_DIR,UPLOAD_DIR,workspace/'ytdlp',workspace/'ytdl_downloads']
        if any(d.resolve().parent != workspace or d.is_symlink() or (d.exists() and getattr(d.lstat(),'st_file_attributes',0)&1024) for d in target_dirs):
            raise ValueError('Temizleme klasörü proje dışında; işlem durduruldu.')
        deleted_db_rows = 0
        with closing(sqlite3.connect(str(FAVORITES_DB_PATH))) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM lyrics;")
            row = cursor.fetchone()
            if row:
                deleted_db_rows = row[0]
            cursor.execute("DELETE FROM lyrics;")
            cursor.execute("DELETE FROM lyrics_history;")
            conn.commit()
            cursor.execute("VACUUM;")

        # Explicit cleanup must also retire disk snapshots, otherwise lyrics can return on reload.
        for key in project_store.all():
            if key.startswith(('lyrics:', 'project:', 'uvr-stem-settings:', 'uvr-lyrics-draft:', 'uvr-history:', 'uvr-passages-v2:', 'uvr-passages-v3:')):
                project_store.put(key, None)
        library=json.loads(project_store.get('uvr_library') or '[]')
        project_store.update_library('[]',[item['id'] for item in library])
        audio_jobs.clear_cache_and_history()

        deleted_files = 0
        for d in target_dirs:
            if d.exists() and d.is_dir():
                for item in d.iterdir():
                    try:
                        if item.is_file():
                            item.unlink(missing_ok=True)
                            deleted_files += 1
                        elif item.is_dir():
                            shutil.rmtree(item)
                            deleted_files += 1
                    except Exception as e:
                        raise RuntimeError(f"{item.name} temizlenemedi: {e}") from e

        # Ensure required directories still exist
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(YTL_DIR, exist_ok=True)
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        return {
            "status": "success",
            "message": "Outputs, Yt-Dlp indirmeleri, yüklemeler ve karaoke veritabanı başarıyla temizlendi.",
            "deleted_lyrics_count": deleted_db_rows,
            "deleted_files_count": deleted_files
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

_lyrics_inference_lock = threading.RLock()


class SyllablesRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=256)
    segment: LyricSegmentModel


class DeepWordsRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=256)
    start: float = Field(..., ge=0, allow_inf_nan=False)
    end: float = Field(..., gt=0, allow_inf_nan=False)


def run_deep_words(task_id, req):
    try:
        from karaoke_deep_words import deep_words
        with _lyrics_inference_lock:
            result=deep_words(_find_audio_file(req.file_name),req.start,req.end,get_precision_whisper_model,
                lambda p,m:_update_task(task_id,progress=p,message=m))
        _update_task(task_id,status='completed',progress=1.,result=result)
    except Exception as exc:
        _update_task(task_id,status='failed',error=str(exc),message='Çözümleme tamamlanamadı; mevcut sözler korundu.')


def get_precision_whisper_model(key):
    # Call only under the lyrics inference lock. Keep one large model resident.
    for other in list(_whisper_cache):
        if other != key:
            del _whisper_cache[other]
    return get_whisper_model(key)


@app.post('/api/lyrics/deep-words')
def deep_words_endpoint(req: DeepWordsRequest, background_tasks: BackgroundTasks):
    _find_audio_file(req.file_name)
    if req.end<=req.start or req.end-req.start>60:
        raise HTTPException(status_code=422,detail='En fazla 60 saniyelik geçerli bir aralık seçin.')
    task_id=_create_task({'message':'Ayrıntılı söz çözümlemesi sırada...'})
    background_tasks.add_task(run_deep_words,task_id,req)
    return {'task_id':task_id}


@app.post('/api/lyrics/syllables')
def syllables_endpoint(req: SyllablesRequest):
    from karaoke_syllables import detect_syllables
    audio_path = _find_audio_file(req.file_name)
    if not _lyrics_inference_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail='Başka bir hizalama çalışıyor. Tamamlanınca tekrar deneyin.')
    try:
        return detect_syllables(audio_path, req.segment.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail='Hece tespiti tamamlanamadı. Mevcut sözler ve bağlantılar korundu.')
    finally:
        _lyrics_inference_lock.release()


def _lyrics_revision(file_name):
    current = get_saved_lyrics(file_name)
    return hashlib.sha256(json.dumps(current.get("segments", []) if current else [], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class LyricsAISettings(BaseModel):
    api_key: Optional[str] = Field(None,max_length=512)
    enabled: bool = False


@app.middleware('http')
async def protect_lyrics_ai_settings(request, call_next):
    if request.url.path.startswith('/api/settings/lyrics-ai') or request.url.path in ('/api/lyrics/ai-review','/api/lyrics/ai-transcribe'):
        origin=request.headers.get('origin')
        if origin and origin not in {'http://localhost:3000','http://127.0.0.1:3000','http://localhost:8000','http://127.0.0.1:8000'}:
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'Bu işlem yalnız yerel uygulamadan kullanılabilir.'},status_code=403)
    return await call_next(request)


@app.get('/api/settings/lyrics-ai')
def lyrics_ai_settings():
    from lyrics_ai import public_settings
    return public_settings()


@app.put('/api/settings/lyrics-ai')
def update_lyrics_ai_settings(req: LyricsAISettings):
    from lyrics_ai import save_settings
    try:return save_settings(req.api_key,req.enabled)
    except ValueError:raise HTTPException(400,'API anahtarının biçimi geçersiz.')


@app.post('/api/settings/lyrics-ai/test')
def test_lyrics_ai_settings():
    from lyrics_ai import settings,generate
    try:
        key=settings().get('api_key')
        if not key:raise ValueError('Önce API anahtarını kaydedin.')
        generate('Yalnız OK yaz.',key)
        return {'ok':True}
    except ValueError as exc:raise HTTPException(400,str(exc))


class LyricsAIReview(BaseModel):
    file_name: str = Field(...,min_length=1,max_length=256)
    segments: List[LyricSegmentModel] = Field(...,min_length=1,max_length=500)


class LyricsAITranscribe(BaseModel):
    file_name: str = Field(...,min_length=1,max_length=256)


def run_ai_transcription(task_id,req):
    try:
        from lyrics_ai import settings,transcribe_audio
        config=settings()
        if not config.get('api_key'):raise ValueError('Önce ayarlardan API anahtarını kaydedin.')
        result=transcribe_audio(_find_audio_file(req.file_name),config['api_key'],
            progress=lambda p,m:_update_task(task_id,progress=p,message=m))
        # A draft has approximate segment times, never verified word timings.
        _update_task(task_id,status='completed',progress=1.,result=result)
    except Exception as exc:_update_task(task_id,status='failed',error=str(exc),message='Gemini söz taslağı oluşturulamadı; kayıtlı sözler korundu.')


@app.post('/api/lyrics/ai-transcribe')
def ai_transcribe_endpoint(req: LyricsAITranscribe,background_tasks: BackgroundTasks):
    _find_audio_file(req.file_name)
    task_id=_create_task({'message':'Gemini vokal kaydını dinlemeye hazırlanıyor...'})
    background_tasks.add_task(run_ai_transcription,task_id,req)
    return {'task_id':task_id}


def run_ai_review(task_id,req,expected_revision):
    try:
        from lyrics_ai import correct_rows
        with _lyrics_inference_lock:
            result,report=correct_rows(_find_audio_file(req.file_name),[s.model_dump() for s in req.segments],
                get_precision_whisper_model,lambda p,m:_update_task(task_id,progress=p,message=m))
            if report is None:raise ValueError('AI desteğini ayarlardan açıp API anahtarını kaydedin.')
            with _lyrics_data_lock:
                if _lyrics_revision(req.file_name)!=expected_revision:raise ValueError('İnceleme sırasında sözler değişti; yeni düzenlemeler korundu.')
                saved=save_lyrics_db(req.file_name,'tr',result,is_edited=True)
            saved['ai_report']=report
            _update_task(task_id,status='completed',progress=1.,result=saved)
    except Exception as exc:
        _update_task(task_id,status='failed',error=str(exc),message='AI incelemesi uygulanamadı; mevcut sözler korundu.')


@app.post('/api/lyrics/ai-review')
def ai_review_endpoint(req: LyricsAIReview,background_tasks: BackgroundTasks):
    _find_audio_file(req.file_name)
    from lyrics_ai import public_settings
    config=public_settings()
    if not config['enabled'] or not config['configured']:raise HTTPException(400,'Önce ayarlardan AI desteğini açıp anahtarı kaydedin.')
    task_id=_create_task({'message':'Gemini incelemesi sırada...'})
    background_tasks.add_task(run_ai_review,task_id,req,_lyrics_revision(req.file_name))
    return {'task_id':task_id}


def run_lyrics_alignment(task_id: str, req: LyricsRequest, expected_revision: str):
    try:
        with _lyrics_inference_lock:
            _update_task(task_id, message="Vokal ses ve kelimeler hazırlanıyor...", progress=0.1)
            audio_path = _find_audio_file(req.file_name)
            # Only consider candidates that actually change the stem name.
            # Previously an unchanged replacement could select the instrumental itself.
            for pattern in ("instrumental", "other", "inst"):
                if re.search(pattern, audio_path.name, re.IGNORECASE):
                    for replacement in ("Vocals", "vocals", "vocal"):
                        name = re.sub(pattern, replacement, audio_path.name, flags=re.IGNORECASE)
                        candidate = audio_path.with_name(name)
                        if name != audio_path.name and candidate.is_file():
                            audio_path = candidate
                            break
                    break
            model = get_whisper_model(req.model_name if req.model_name in ("large-v3", "large-v3-turbo") else "large-v3")
            language = None if req.language in (None, "", "auto", "none") else req.language
            transcript = (req.raw_lyrics_text or "").strip()
            paste_report=None
            if language is None or (not transcript and language != 'tr'):
                _update_task(task_id, message="Sözler ve dil tanınıyor...", progress=0.2)
                decoded, info = model.transcribe(str(audio_path), language=language,
                    word_timestamps=False, vad_filter=False, condition_on_previous_text=False,
                    beam_size=5, temperature=0.0)
                decoded = list(decoded)
                language = language or info.language
                if not transcript and language != 'tr':
                    transcript = "\n".join(seg.text.strip() for seg in decoded if seg.text.strip())
            if language == 'tr':
                from karaoke_anchored import recognize_anchored, anchor_transcript, anchor_transcript_rows
                model=None
                try:
                    segments=recognize_anchored(audio_path,get_precision_whisper_model,
                        lambda fraction,message:_update_task(task_id,progress=.2+.7*fraction,message=message))
                except ValueError:
                    if not transcript:raise
                    segments=[]
                if transcript:
                    try:
                        segments=anchor_transcript(transcript,segments)
                    except ValueError:
                        segments,paste_report=anchor_transcript_rows(transcript,segments,
                            lambda fraction,message:_update_task(task_id,progress=.85+.05*fraction,message=message))
            elif not transcript:
                raise ValueError("Ses içinde söz bulunamadı; mevcut kayıt korundu.")
            else:
                _update_task(task_id, message="Tüm kelimeler vokal sesle hizalanıyor...", progress=0.5)
                try:
                    segments = align_lyrics(model, audio_path, transcript, language)
                    from karaoke_anchored import bounded_refine
                    segments = bounded_refine(audio_path,segments,language,refine_turkish)
                except ValueError:
                    if not req.raw_lyrics_text:raise
                    from karaoke_anchored import anchor_transcript_rows
                    decoded,_=model.transcribe(str(audio_path),language=language,word_timestamps=True,
                        condition_on_previous_text=False,beam_size=5,temperature=0.)
                    recognized=[{'words':[{'word':w.word.strip(),'start':w.start,'end':w.end,
                        'probability':w.probability,'timing_source':'whisper','needs_review':True}
                        for w in seg.words or [] if w.probability>=.6 and w.end>w.start]} for seg in decoded]
                    segments,paste_report=anchor_transcript_rows(transcript,recognized,
                        lambda fraction,message:_update_task(task_id,progress=.85+.05*fraction,message=message))
            # Short display lines without changing ANY word boundary.
            if not req.raw_lyrics_text:
                grouped = []
                for seg in segments:
                    words = seg["words"]
                    for i in range(0, len(words), 6):
                        chunk = words[i:i + 6]
                        grouped.append({"start": chunk[0]["start"], "end": chunk[-1]["end"],
                                        "text": " ".join(w["word"] for w in chunk), "words": chunk})
                segments = grouped
            from lyrics_ai import correct_rows
            ai_report=None
            if not req.raw_lyrics_text:
                segments,ai_report=correct_rows(audio_path,segments,get_precision_whisper_model,
                    lambda p,m:_update_task(task_id,progress=.9+.08*p,message=m))
            with _lyrics_data_lock:
                if _lyrics_revision(req.file_name) != expected_revision:
                    raise ValueError("Hizalama sırasında sözler değiştirildi. Yeni düzenlemeler korundu; yeniden hizalayın.")
                saved = save_lyrics_db(req.file_name, language, segments, is_edited=False)
            saved["cached"] = False
            saved['ai_report']=ai_report
            saved['paste_report']=paste_report
            _update_task(task_id, status="completed", progress=1.0, result=saved,
                         message="Hizalama tamamlandı; şüpheli zamanlar işaretlendi." if saved["timing_issues"] else "Kelime hizalaması tamamlandı.")
    except Exception as exc:
        _update_task(task_id, status="failed", error=str(exc), message="Hizalama tamamlanamadı; mevcut kayıt korundu.")


@app.post("/transcribe_lyrics")
def transcribe_lyrics_endpoint(req: LyricsRequest, background_tasks: BackgroundTasks):
    if not req.force and not req.raw_lyrics_text:
        cached = get_saved_lyrics(req.file_name)
        if cached and cached.get("segments"):
            return cached
    _find_audio_file(req.file_name)
    task_id = _create_task({"message": "Kelime hizalaması sıraya alındı..."})
    background_tasks.add_task(run_lyrics_alignment, task_id, req, _lyrics_revision(req.file_name))
    return {"task_id": task_id, "status": "processing"}


def run_pasted_sync(task_id,req,expected_revision):
    from paste_sync import synchronize
    from karaoke_anchored import anchor_transcript_rows
    try:
        text=(req.raw_lyrics_text or '').strip()
        acquired=_lyrics_inference_lock.acquire(timeout=1)
        try:
            if acquired:
                path=_find_audio_file(req.file_name)
                segments,report=synchronize(path,text,req.language,
                    lambda p,m:_update_task(task_id,progress=p,message=m))
            else:
                segments,report=anchor_transcript_rows(text,[])
                report.update(attempts=0,reason='Ses motoru meşgul; sözler bekletilmeden eklendi.')
        finally:
            if acquired:_lyrics_inference_lock.release()
        with _lyrics_data_lock:
            if _lyrics_revision(req.file_name)!=expected_revision:raise ValueError('Sözler değiştirildi; yeni düzenlemeler korundu.')
            saved=save_lyrics_db(req.file_name,req.language or 'tr',segments,is_edited=True)
        saved.update(cached=False,paste_report=report)
        _update_task(task_id,status='completed',progress=1.,result=saved,message='Sözler satır satır eklendi. Eşleşmeyen satırlar senkron bekliyor.')
    except Exception as exc:_update_task(task_id,status='failed',error=str(exc),message='Sözler kaydedilemedi; mevcut kayıt korundu.')


@app.post('/api/lyrics/paste')
def paste_lyrics_endpoint(req: LyricsRequest,background_tasks: BackgroundTasks):
    text=(req.raw_lyrics_text or '').strip()
    if not text or len(text)>100000 or len(text.splitlines())>500:raise HTTPException(422,'1–500 satır söz yapıştırın.')
    _find_audio_file(req.file_name)
    task_id=_create_task({'message':'Sözler hazırlanıyor · en fazla 4 deneme','model_type':'paste_sync'})
    background_tasks.add_task(run_pasted_sync,task_id,req,_lyrics_revision(req.file_name))
    return {'task_id':task_id,'status':'processing'}


class QuickCleanRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=256)
    clean_type: str = Field(..., pattern="^(dereverb|debleed)$")
    out_format: Optional[str] = "flac"

@app.post("/quick_clean")
async def quick_clean_endpoint(req: QuickCleanRequest, background_tasks: BackgroundTasks):
    try:
        audio_path = _find_audio_file(req.file_name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    model_key = "BS-Roformer-De-Reverb" if req.clean_type == "dereverb" else "MelBand Roformer Kim | Inst V2 by Unwa"
    model_type = "roformer"
    
    task_id = _create_task({
        "message": f"Quick Clean: {'De-Reverb' if req.clean_type=='dereverb' else 'De-Bleed'} running...",
        "model_type": model_type,
        "clean_type": req.clean_type
    })
    
    sep_req = SeparationRequest(
        model_type=model_type,
        model_key=model_key,
        audio_path=str(audio_path),
        out_format=req.out_format if req.out_format else "mp3",
        params={"overlap": 8, "segment_size": 256, "normalization_threshold": 0.9}
    )
    background_tasks.add_task(run_separation_task, task_id, sep_req)
    return {"task_id": task_id}

class VisualizerRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=256)
    aspect_ratio: str = Field(default="9:16", pattern="^(9:16|16:9)$")
    theme: str = Field(default="neon", pattern="^(neon|gold|cyberpunk)$")
    title: Optional[str] = "UVR5 Studio Audio"

@app.post("/generate_visualizer")
async def generate_visualizer_endpoint(req: VisualizerRequest):
    try:
        audio_path = _find_audio_file(req.file_name)
            
        out_video_name = f"Visualizer_{Path(req.file_name).stem}_{req.theme}_{int(time.time())}.mp4"
        out_video_path = _safe_join_and_check(OUTPUT_DIR, out_video_name)
        
        if req.aspect_ratio == "9:16":
            width, height = 1080, 1920
            wave_w, wave_h = 960, 480
        else:
            width, height = 1920, 1080
            wave_w, wave_h = 1600, 400
            
        if req.theme == "gold":
            wave_color = "#f59e0b|#fbbf24|#d97706"
            bg_color = "0x0B0F19"
        elif req.theme == "cyberpunk":
            wave_color = "#ec4899|#8b5cf6|#06b6d4"
            bg_color = "0x050510"
        else:
            wave_color = "#6366f1|#38bdf8|#818cf8"
            bg_color = "0x090D16"

        filter_complex = (
            f"[0:a]showwaves=s={wave_w}x{wave_h}:mode=line:colors={wave_color}:scale=cbrt[waves];"
            f"color=c={bg_color}:s={width}x{height}:d=600[bg];"
            f"[bg][waves]overlay=(W-w)/2:(H-h)/2:shortest=1[v]"
        )
        
        cmd = [
            "ffmpeg", "-y",
            "-i", str(audio_path),
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "0:a",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(out_video_path)
        ]
        
        subprocess.run(cmd, check=True, capture_output=True, creationflags=SUBPROCESS_FLAGS)
        return {"status": "success", "video_file": out_video_name, "download_url": f"/output/{out_video_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class KaraokeVideoRequest(BaseModel):
    timing_file: Optional[str] = None
    inst_file: str = Field(..., min_length=1, max_length=256)
    segments: List[LyricSegmentModel]
    title: Optional[str] = ""
    artist: Optional[str] = ""
    header_text: Optional[str] = ""
    show_header: Optional[bool] = True
    aspect_ratio: str = Field(default="16:9", pattern="^(16:9|9:16)$")
    theme: str = Field(default="gold", pattern="^(gold|neon|cyberpunk|emerald)$")

def run_karaoke_video_task(task_id: str, req_data: dict):
    reserved_video = None
    try:
        _update_task(task_id, status="processing", message="Karaoke ASS altyazıları oluşturuluyor...", progress=0.1)
        req = KaraokeVideoRequest(**req_data)
        inst_path = _find_audio_file(req.inst_file)
        if req.timing_file:
            import soundfile as sf
            timing_path = _find_audio_file(req.timing_file)
            source_info, target_info = sf.info(str(timing_path)), sf.info(str(inst_path))
            if abs(source_info.duration - target_info.duration) > 0.02:
                raise ValueError("Vokal ve enstrümantal süreleri farklı. Aynı ayrıştırmanın eşleşen dosyalarını kullanın.")
        issues = timing_issues([s.model_dump() for s in req.segments], require_words=False, include_review=False)
        if issues:
            raise ValueError(" / ".join(issues[:5]))
        
        is_vertical = req.aspect_ratio == "9:16"
        res_x, res_y = (1080, 1920) if is_vertical else (1920, 1080)
        
        # Color palette per theme (100% Solid Full-Opacity Colors)
        if req.theme == "gold":
            primary_color = "&H0000D7FF"     # Glowing Gold BGR (Active Karaoke Fill)
            upcoming_color = "&H00D8D8D8"    # 100% Solid Crisp Silver-White
            break_color = "&H0000D7FF"
            wave_color = "#f59e0b|#fbbf24|#d97706"
            bg_color = "0x070A12"
        elif req.theme == "cyberpunk":
            primary_color = "&H00D946EF"     # Glowing Neon Magenta (Active Karaoke Fill)
            upcoming_color = "&H00D8D8D8"
            break_color = "&H00D946EF"
            wave_color = "#ec4899|#c084fc|#8b5cf6"
            bg_color = "0x090514"
        elif req.theme == "emerald":
            primary_color = "&H0034D399"     # Emerald Green (Active Karaoke Fill)
            upcoming_color = "&H00D8D8D8"
            break_color = "&H0034D399"
            wave_color = "#10b981|#34d399|#059669"
            bg_color = "0x040D0A"
        else: # neon
            primary_color = "&H00FFFF00"     # Cyan Blue (Active Karaoke Fill)
            upcoming_color = "&H00D8D8D8"
            break_color = "&H00FFFF00"
            wave_color = "#06b6d4|#38bdf8|#3b82f6"
            bg_color = "0x060914"

        to_ass_time = ass_time

        # 16:9 / 9:16 Optimized typography and line spacing
        font_size_active = 70 if is_vertical else 76
        font_size_upcoming = 34 if is_vertical else 30
        margin_v_active = 860 if is_vertical else 420
        margin_v_upcoming = 700 if is_vertical else 310
        x_center = res_x // 2
        y_active = 1010 if is_vertical else 550
        y_upcoming = 1260 if is_vertical else 750

        ass_lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {res_x}",
            f"PlayResY: {res_y}",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: Title, Segoe UI, 32, &H00FFFFFF, &H00000000, &H00000000, &H80000000, -1, 0, 0, 0, 100, 100, 1, 0, 1, 0, 0, 7, 110, 110, 85, 1",
            f"Style: BreakNotice, Arial, 44, {break_color}, &H00000000, &H00000000, &H90000000, -1, 1, 0, 0, 100, 100, 2, 0, 1, 4, 3, 2, 80, 80, {margin_v_active}, 1",
            f"Style: BreathCue, Arial, 32, &H00A8FFB2, &H00000000, &H00000000, &H90000000, -1, 0, 0, 0, 100, 100, 2, 0, 1, 3, 2, 2, 80, 80, {margin_v_active + 70}, 1",
            f"Style: Active, Segoe UI, {font_size_active}, {primary_color}, &H00FFFFFF, &H00000000, &H90000000, -1, 0, 0, 0, 100, 100, 0, 0, 1, 1, 0, 2, 120, 120, {margin_v_active}, 1",
            f"Style: Upcoming, Segoe UI, {font_size_upcoming}, &H009C9595, &H00000000, &H00000000, &H80000000, 0, 0, 0, 0, 100, 100, 0, 0, 1, 0, 0, 2, 120, 120, {margin_v_upcoming}, 1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
        ]

        if req.show_header is not False:
            parts = []
            if req.header_text and req.header_text.strip():
                parts.append(req.header_text.strip())
            song_info = []
            if req.title and req.title.strip():
                song_info.append(req.title.strip())
            if req.artist and req.artist.strip():
                song_info.append(req.artist.strip())
            if song_info:
                song_str = " - ".join(song_info)
                title_text = f"{parts[0]} • {song_str}" if parts else song_str
            elif parts:
                title_text = parts[0]
            else:
                title_text = ""
            title_text = escape_ass(title_text)
            if title_text:
                ass_lines.append(f"Dialogue: 0,0:00:00.00,1:00:00.00,Title,,0,0,0,,{title_text}")

        segments_to_use = req.segments
        if (not segments_to_use or len(segments_to_use) == 0):
            cached = get_saved_lyrics(req.inst_file)
            if cached and cached.get("segments"):
                segments_to_use = [LyricSegmentModel(**s) for s in cached["segments"]]
        elif segments_to_use and len(segments_to_use) > 0:
            save_lyrics_db(req.inst_file, "tr", [s.model_dump() for s in segments_to_use], is_edited=True)

        windows = render_windows([s.model_dump() for s in segments_to_use])
        segments_to_use = [LyricSegmentModel(**s) for s, _ in windows]
        from karaoke_timing import solo_windows
        import soundfile as sf
        for solo_start,solo_end in solo_windows([s.model_dump() for s in segments_to_use],sf.info(str(inst_path)).duration):
            ass_lines.append(f"Dialogue: 0,{to_ass_time(solo_start)},{to_ass_time(solo_end)},BreakNotice,,0,0,0,,{{\\pos({x_center}, {y_active})}}Solo...")

        if segments_to_use and segments_to_use[0].start >= 1.5:
            first_seg = segments_to_use[0]
            first_text = escape_ass(first_seg.text.strip())
            if first_text:
                ass_lines.append(f"Dialogue: 0,0:00:00.00,{to_ass_time(first_seg.start)},Upcoming,,0,0,0,,{{\\pos({x_center}, {y_upcoming})}}{first_text}")

        for idx, seg in enumerate(segments_to_use):
            raw_text = escape_ass(seg.text.strip())
            if not raw_text:
                continue

            st = to_ass_time(seg.start)
            act_end_sec = windows[idx][1]
            en = to_ass_time(act_end_sec)

            active_karaoke_text = ass_word_tags(seg.model_dump())
            if idx == 0 and seg.start < 1.5:
                active_anim = f"{{\\pos({x_center}, {y_active})\\fad(0, 200)}}"
            else:
                active_anim = f"{{\\pos({x_center}, {y_active})\\fad(0, 200)}}"

            from karaoke_design import gradient_masks
            masks = gradient_masks(req.theme, res_x, res_y, y_active, font_size_active) if seg.words else ['']
            for mask in masks:
                ass_lines.append(f"Dialogue: 1,{st},{en},Active,,0,0,0,,{active_anim}{mask}{active_karaoke_text}")
            if idx + 1 < len(segments_to_use):
                next_seg = segments_to_use[idx + 1]
                next_text = escape_ass(next_seg.text.strip())
                if next_text and next_seg.start > seg.start:
                    ass_lines.append(f"Dialogue: 0,{st},{to_ass_time(next_seg.start)},Upcoming,,0,0,0,,{{\\pos({x_center}, {y_upcoming})}}{next_text}")

        from karaoke_design import ambient_events, progress_events
        import soundfile as sf
        ass_lines.extend(ambient_events(sf.info(str(inst_path)).duration,res_x,res_y))
        ass_lines.extend(progress_events(sf.info(str(inst_path)).duration,res_x,req.theme))
        timestamp_id = uuid.uuid4().hex
        ass_filename = f"karaoke_sub_{timestamp_id}.ass"
        ass_path = OUTPUT_DIR / ass_filename
        ass_path.write_text("\n".join(ass_lines), encoding="utf-8")

        from video_filename import reserve_video_path
        from urllib.parse import quote
        reserved_video = reserve_video_path(
            OUTPUT_DIR, artist=req.artist, title=req.title, label=req.header_text,
            fallback=Path(req.inst_file).stem,
        )
        out_video_name = reserved_video.name

        from karaoke_design import studio_background
        backdrop = studio_background(OUTPUT_DIR, req.theme, is_vertical)
        freq_w = 840 if is_vertical else 1600
        freq_h = 64 if is_vertical else 48
        freq_y = 1760 if is_vertical else 920

        filter_complex = (
            f"[0:a]aformat=channel_layouts=mono,showwaves=s={freq_w}x{freq_h}:r=30:mode=line:draw=full:scale=sqrt:colors={wave_color},format=rgba,colorkey=0x000000:0.1:0.1,gblur=sigma=0.7,split[sharp][soft];"
            f"[soft]gblur=sigma=7[glow];[glow][sharp]overlay=0:0[freqs];"
            f"[1:v]fps=30,format=rgba[stage];"
            f"[stage][freqs]overlay=(W-w)/2:{freq_y}:shortest=1[v_raw];"
            f"[v_raw]subtitles=filename={ass_filename}[v]"
        )

        _update_task(task_id, status="processing", message="FFmpeg 1080p Video Render Ediliyor...", progress=0.3)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(inst_path.resolve()),
            "-loop", "1", "-i", str(backdrop.resolve()),
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "0:a",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-threads", "0",
            "-crf", "22",
            "-r", "30",
            "-profile:v", "main",
            "-level:v", "4.0",
            "-g", "30",
            "-keyint_min", "30",
            "-sc_threshold", "0",
            "-maxrate", "8M",
            "-bufsize", "16M",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-c:a", "aac",
            "-b:a", "320k",
            "-shortest",
            str(out_video_name)
        ]

        proc = subprocess.run(cmd, cwd=str(OUTPUT_DIR), capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg render failed: {proc.stderr[-400:]}")

        _update_task(
            task_id, 
            status="completed", 
            progress=1.0, 
            message="1080p Karaoke Videosu Başarıyla Oluşturuldu!", 
            video_file=out_video_name,
            download_url=f"/output/{quote(out_video_name, safe='')}"
        )
    except Exception as e:
        if reserved_video is not None:
            try:
                reserved_video.unlink(missing_ok=True)
            except OSError:
                pass
        _update_task(task_id, status="failed", error=str(e), message=f"Render Hatası: {e}")

@app.post("/generate_karaoke_video")
async def generate_karaoke_video_endpoint(req: KaraokeVideoRequest, background_tasks: BackgroundTasks):
    req.segments = [LyricSegmentModel(**s) for s in repair_timing([s.model_dump() for s in req.segments])]
    issues = timing_issues([s.model_dump() for s in req.segments], require_words=False, include_review=False)
    if not req.segments or issues:
        raise HTTPException(status_code=422, detail=" / ".join(issues[:5]) or "Sözler eksik")
    task_id = _create_task({"message": "Karaoke Videosu Hazırlanıyor...", "model_type": "karaoke_video"})
    background_tasks.add_task(run_karaoke_video_task, task_id, req.model_dump())
    return {"task_id": task_id, "status": "processing"}


@app.get('/api/karaoke/background')
def karaoke_background(theme: str = 'gold', vertical: bool = False):
    from karaoke_design import studio_background
    return FileResponse(studio_background(OUTPUT_DIR, theme, vertical), media_type='image/png')

@app.api_route("/clear_memory", methods=["GET", "POST", "OPTIONS"])
async def clear_memory_endpoint():
    """
    Cleans up all cached models (AudioSR, Whisper, Separator) from GPU VRAM and RAM,
    forces Python cycle garbage collection, releases CUDA reserved blocks to the OS,
    and returns real-time GPU memory metrics.
    """
    unload_whisper_models()
    core.clear_gpu_and_ram_cache(deep=True)

    import torch
    gpu_info = {}
    if torch.cuda.is_available():
        try:
            gpu_info = {
                "allocated_mb": round(torch.cuda.memory_allocated() / (1024 * 1024), 2),
                "reserved_mb": round(torch.cuda.memory_reserved() / (1024 * 1024), 2),
                "max_allocated_mb": round(torch.cuda.max_memory_allocated() / (1024 * 1024), 2),
                "device_name": torch.cuda.get_device_name(0) if torch.cuda.device_count() > 0 else "CUDA"
            }
        except Exception:
            pass
    return {
        "status": "success",
        "message": "Ekran kartı belleği (VRAM) ve sistem RAM'i başarıyla tamamen serbest bırakıldı.",
        "gpu": gpu_info
    }

from service_control import revision as service_revision
LOADED_REVISION=service_revision()

@app.get('/api/service')
def local_service_status():
    return {'root':str(Path(__file__).resolve().parent),'pid':os.getpid(),'revision':LOADED_REVISION}

@app.post('/api/service/prepare')
def prepare_service_stop():
    with tasks_lock:
        if any(t.get('status')=='processing' for t in tasks.values()):raise HTTPException(409,'Çalışan işlem var. Önce tamamlanmasını bekleyin.')
    if any(j['status'] in ('queued','processing','cancelling') for j in audio_jobs.list()):raise HTTPException(409,'Ses kuyruğunu önce tamamlayın veya iptal edin.')
    return {'ready':True}

@app.post('/api/service/restart')
def restart_local_service(background_tasks: BackgroundTasks):
    prepare_service_stop()
    background_tasks.add_task(_launch_service_control,'restart')
    return {'status':'restarting','previous_pid':os.getpid()}

def _launch_service_control(action):
    time.sleep(.5)
    subprocess.Popen([sys.executable,str(Path(__file__).parent/'service_control.py'),action],cwd=Path(__file__).parent,
        stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=(subprocess.CREATE_NO_WINDOW|subprocess.DETACHED_PROCESS|subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0,
        start_new_session=os.name!='nt')

@app.post('/shutdown')
def shutdown_system_endpoint(background_tasks: BackgroundTasks):
    prepare_service_stop()
    background_tasks.add_task(_launch_service_control,'stop')
    return {'status':'shutdown_initiated'}

class RestoreAudioRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=256)
    denoise: bool = True
    enhance_sr: bool = True
    ddim_steps: int = Field(default=20, ge=5, le=100)
    guidance_scale: float = Field(default=3.5, ge=1.0, le=10.0)

def run_restoration_task(task_id: str, req_data: dict):
    try:
        _update_task(task_id, status="processing", message="AI Restorasyon motoru hazırlanıyor...", progress=0.02)
        req = RestoreAudioRequest(**req_data)
        audio_path = _find_audio_file(req.file_name)
        
        def progress_cb(p: float, msg: str):
            _update_task(task_id, status="processing", progress=round(p, 2), message=msg)
            
        output_path = core.restore_audio_pipeline(
            str(audio_path.resolve()),
            output_dir=str(OUTPUT_DIR.resolve()),
            denoise=req.denoise,
            enhance_sr=req.enhance_sr,
            ddim_steps=req.ddim_steps,
            guidance_scale=req.guidance_scale,
            progress_callback=progress_cb
        )
        
        out_file = Path(output_path).name
        _update_task(
            task_id,
            status="completed",
            progress=1.0,
            message="Restorasyon başarıyla tamamlandı!",
            output_file=out_file,
            download_url=f"/output/{out_file}",
            stem_file=out_file,
            stems=[out_file]
        )
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        try:
            print(f"[Restoration Error] {err_msg}")
        except Exception:
            pass
        _update_task(task_id, status="failed", error=str(e), message=f"Restorasyon hatası: {str(e)}")
    finally:
        core.clear_gpu_and_ram_cache(deep=True)

@app.post("/restore_audio")
async def start_restore_audio(req: RestoreAudioRequest, background_tasks: BackgroundTasks):
    audio_path = _find_audio_file(req.file_name)
    _validate_audio_path(str(audio_path))
    task_id = _create_task({
        "message": "AI Restorasyon başlatılıyor...",
        "model_type": "restore_audiosr"
    })
    background_tasks.add_task(run_restoration_task, task_id, req.dict())
    return {"task_id": task_id}

# Close stray WebSocket connections (e.g. from browser extensions).
@app.websocket("/{path:path}")
async def websocket_catch_all(websocket: WebSocket, path: str):
    await websocket.accept()
    await websocket.close()

# The only UI is the Next.js app; this process serves its API.
@app.get("/", include_in_schema=False)
async def serve_index():
    return RedirectResponse('http://localhost:3000/')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
