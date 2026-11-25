"""Lambda(Claude) 분석 모드: 내부 결과 API, worker 비활성, 재분석 재트리거, Lambda 핸들러."""
import importlib.util
import io
import json
import sys
import types
from pathlib import Path

import pytest
from sqlalchemy import select

from backend.app import main, worker
from backend.app.config import settings
from backend.app.models import AnalysisJob, AnalysisRun, Photo
from backend.tests.test_api_integration import api, post_photo  # noqa: F401  (fixture 재사용)

TOKEN = 'test-internal-token'


@pytest.fixture
def lambda_mode(api, monkeypatch):
    monkeypatch.setattr(settings, 'face_analysis_provider', 'lambda')
    monkeypatch.setattr(settings, 'internal_api_token', TOKEN)
    return api


def display_key(photo):
    return f"moacut/albums/{photo['album_id']}/photos/{photo['id']}/display.jpg"


def send(client, payload, token=TOKEN):
    return client.post('/api/internal/analysis-results', json=payload, headers={'X-Internal-Token': token})


def test_result_is_saved_and_filters_use_people_count(lambda_mode):
    owner, member, outsider, album, samples, factory, storage = lambda_mode
    photo = post_photo(owner, album, samples, 'landscape')
    assert worker.process_one() is False  # worker never claims jobs in Lambda mode
    response = send(outsider, {'key': display_key(photo), 'scene': '바다', 'tags': ['바다', '모래', ' '],
                                'people_count': 2, 'model': 'claude-test', 'elapsed_ms': 900})
    assert response.status_code == 200, response.text
    detail = owner.get(f"/api/photos/{photo['id']}").json()
    assert detail['analysis_status'] == 'completed' and detail['analysis_provider'] == 'claude'
    assert detail['tags'] == ['바다', '모래'] and detail['face_count'] == 2 and detail['people'] == []
    group = owner.get(f"/api/albums/{album['id']}/photos?filter=group").json()
    assert [item['id'] for item in group['items']] == [photo['id']]
    assert owner.get(f"/api/albums/{album['id']}/photos?filter=review").json()['total'] == 0
    with factory() as db:
        assert db.scalar(select(AnalysisJob).where(AnalysisJob.photo_id == photo['id'])).status == 'completed'
        assert db.scalar(select(AnalysisRun).where(AnalysisRun.photo_id == photo['id'])).provider == 'claude'


def test_token_key_and_missing_photo_are_rejected(lambda_mode, monkeypatch):
    owner, _, _, album, samples, _, _ = lambda_mode
    photo = post_photo(owner, album, samples, 'landscape')
    assert send(owner, {'key': display_key(photo)}, token='wrong').status_code == 401
    assert send(owner, {'key': f"albums/{album['id']}/photos/{photo['id']}/original"}).status_code == 422
    missing = dict(photo, id='00000000-0000-0000-0000-000000000000')
    assert send(owner, {'key': display_key(missing)}).status_code == 404
    monkeypatch.setattr(settings, 'internal_api_token', '')
    assert send(owner, {'key': display_key(photo)}).status_code == 404


def test_failure_then_reanalyze_retriggers_s3(lambda_mode, monkeypatch):
    owner, _, _, album, samples, _, storage = lambda_mode
    photo = post_photo(owner, album, samples, 'landscape')
    assert send(owner, {'key': display_key(photo), 'error': 'CLAUDE_ANALYSIS_FAILED: HTTPError'}).status_code == 200
    assert owner.get(f"/api/photos/{photo['id']}").json()['analysis_status'] == 'failed'
    touched = []
    monkeypatch.setattr(storage, 'retrigger', touched.append, raising=False)
    response = owner.post(f"/api/photos/{photo['id']}/reanalyze")
    assert response.status_code == 200, response.text
    assert touched == [f"albums/{album['id']}/photos/{photo['id']}/display.jpg"]
    assert send(owner, {'key': display_key(photo), 'scene': '산', 'people_count': 0}).status_code == 200
    assert owner.get(f"/api/photos/{photo['id']}").json()['analysis_status'] == 'completed'


def test_person_reference_does_not_need_face_detection(lambda_mode):
    owner, _, _, album, samples, _, _ = lambda_mode
    response = owner.post(f"/api/albums/{album['id']}/people", data={'name': '나', 'user_id': owner.user['id']},
                          files={'file': ('me.png', samples['landscape'], 'image/png')})
    assert response.status_code == 201, response.text


# --- Lambda handler -----------------------------------------------------------------

def load_handler(monkeypatch):
    fake_boto3 = types.SimpleNamespace(client=lambda *_a, **_k: types.SimpleNamespace(
        get_object=lambda **_: {'Body': io.BytesIO(b'jpeg-bytes')}))
    monkeypatch.setitem(sys.modules, 'boto3', fake_boto3)
    path = Path(__file__).resolve().parents[2] / 'lambda' / 'analyze_photo' / 'handler.py'
    spec = importlib.util.spec_from_file_location('analyze_handler', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in {'CLAUDE_API_KEY': 'k', 'RESULT_URL': 'http://ec2/api/internal/analysis-results',
                        'INTERNAL_API_TOKEN': TOKEN}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(module.time, 'sleep', lambda _s: None)
    return module


class FakeResponse(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *_): return False


def event(key):
    return {'Records': [{'s3': {'bucket': {'name': 'b'}, 'object': {'key': key}}}]}


def test_handler_calls_claude_and_retries_until_photo_exists(monkeypatch):
    handler = load_handler(monkeypatch)
    calls = []

    def fake_urlopen(request, timeout):
        body = json.loads(request.data)
        calls.append((request.full_url, body, dict(request.header_items())))
        if request.full_url == handler.CLAUDE_URL:
            text = '결과입니다 {"scene": "바다", "tags": ["바다", "파도"], "people_count": 3}'
            return FakeResponse(json.dumps({'model': 'claude-x', 'content': [{'type': 'text', 'text': text}]}).encode())
        if sum(url != handler.CLAUDE_URL for url, *_ in calls) == 1:
            raise handler.urllib.error.HTTPError(request.full_url, 404, 'not yet', {}, None)
        return FakeResponse(b'{"status": "completed"}')

    monkeypatch.setattr(handler.urllib.request, 'urlopen', fake_urlopen)
    handler.lambda_handler(event('moacut/albums/a1/photos/p1/display.jpg'), None)
    claude = calls[0]
    assert claude[1]['temperature'] == 0 and claude[1]['messages'][0]['content'][0]['type'] == 'image'
    assert claude[2]['X-api-key'] == 'k'
    results = [body for url, body, _ in calls if url != handler.CLAUDE_URL]
    assert len(results) == 2  # 404 한 번 뒤 재시도
    assert results[-1] | {} == {'key': 'moacut/albums/a1/photos/p1/display.jpg', 'scene': '바다',
                                'tags': ['바다', '파도'], 'people_count': 3, 'model': 'claude-x',
                                'elapsed_ms': results[-1]['elapsed_ms']}


def test_handler_reports_claude_failure_and_skips_other_keys(monkeypatch):
    handler = load_handler(monkeypatch)
    posted = []

    def fake_urlopen(request, timeout):
        if request.full_url == handler.CLAUDE_URL:
            raise handler.urllib.error.HTTPError(request.full_url, 529, 'overloaded', {}, None)
        posted.append(json.loads(request.data))
        return FakeResponse(b'{}')

    monkeypatch.setattr(handler.urllib.request, 'urlopen', fake_urlopen)
    handler.lambda_handler(event('moacut/albums/a1/photos/p1/original'), None)
    assert posted == []
    handler.lambda_handler(event('moacut/albums/a1/photos/p1/display.jpg'), None)
    assert posted[0]['error'].startswith('CLAUDE_ANALYSIS_FAILED')
