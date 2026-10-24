import ast
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient


class OriginalAudioTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.source = Path(self.folder.name) / 'Şarkı #1.wav'
        self.source.write_bytes(b'RIFF-original-audio')
        tree = ast.parse(Path('api_modern.py').read_text(encoding='utf-8'))
        endpoint = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'get_source_audio')
        endpoint.decorator_list = []
        namespace = dict(Path=Path, HTTPException=HTTPException, FileResponse=FileResponse,
                         core=SimpleNamespace(extensions={'.wav'}), _validate_audio_path=lambda path: path)
        exec(compile(ast.Module(body=[endpoint], type_ignores=[]), 'source_endpoint', 'exec'), namespace)
        app = FastAPI()
        app.get('/api/audio/source')(namespace['get_source_audio'])
        self.client = TestClient(app)

    def test_streams_original_and_supports_seeking(self):
        response = self.client.get('/api/audio/source', params={'path': str(self.source)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.source.read_bytes())
        response = self.client.get('/api/audio/source', params={'path': str(self.source)}, headers={'Range': 'bytes=5-12'})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, self.source.read_bytes()[5:13])

    def test_missing_original_returns_404(self):
        self.source.unlink()
        response = self.client.get('/api/audio/source', params={'path': str(self.source)})
        self.assertEqual(response.status_code, 404)

    def test_rejects_non_audio_files(self):
        source = self.source.with_suffix('.txt')
        source.write_text('text')
        response = self.client.get('/api/audio/source', params={'path': str(source)})
        self.assertEqual(response.status_code, 400)
