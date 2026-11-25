"""S3 업로드 이벤트로 실행되어 Claude API로 사진을 분류하고, 결과를 찍 API로 보낸다.

트리거: S3 ObjectCreated, 접미사 `display.jpg` (1600px 이하 JPEG라 Claude 이미지 한도 안에 든다).
외부 패키지 없이 Lambda Python 런타임의 boto3와 표준 라이브러리만 쓴다.

환경 변수
  CLAUDE_API_KEY       강사에게 받은 Claude API 키 (필수)
  RESULT_URL           예: http://<EC2 공인 IP>/api/internal/analysis-results (필수)
  INTERNAL_API_TOKEN   EC2 .env 의 INTERNAL_API_TOKEN 과 같은 값 (필수)
  CLAUDE_MODEL         기본 claude-haiku-5-5
  CLAUDE_TEMPERATURE   기본 0 (분류는 결정적으로). 빈 값이면 보내지 않음
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import boto3

log = logging.getLogger()
log.setLevel(logging.INFO)

CLAUDE_URL = 'https://api.anthropic.com/v1/messages'
PROMPT = (
    '이 여행 사진을 분류해 주세요. 다른 말 없이 JSON 객체 하나만 답하세요.\n'
    '{"scene": "장면을 나타내는 한국어 단어 하나 (예: 바다, 산, 음식, 카페, 야경, 노을, 도시, 실내)",'
    ' "tags": ["사진 속 대상을 나타내는 한국어 단어, 최대 5개"],'
    ' "people_count": 사진에 보이는 사람 수 (정수)}\n'
    '사람이 누구인지는 추측하지 마세요.'
)
DISPLAY_KEY = re.compile(r'(?:.+/)?albums/[^/]+/photos/[^/]+/display\.jpg')

s3 = boto3.client('s3')


def claude_classify(image: bytes) -> dict:
    body = {
        'model': os.environ.get('CLAUDE_MODEL', 'claude-haiku-5-5'),
        'max_tokens': 300,
        'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg',
                                         'data': base64.b64encode(image).decode()}},
            {'type': 'text', 'text': PROMPT},
        ]}],
    }
    temperature = os.environ.get('CLAUDE_TEMPERATURE', '0')
    if temperature != '':
        body['temperature'] = float(temperature)
    request = urllib.request.Request(CLAUDE_URL, data=json.dumps(body).encode(), method='POST', headers={
        'content-type': 'application/json',
        'x-api-key': os.environ['CLAUDE_API_KEY'],
        'anthropic-version': '2023-06-01',
    })
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.load(response)
    text = ''.join(block.get('text', '') for block in data.get('content', []) if block.get('type') == 'text')
    return parse_result(text) | {'model': data.get('model') or body['model']}


def parse_result(text: str) -> dict:
    match = re.search(r'\{.*\}', text, re.S)
    if not match:
        raise ValueError('Claude 응답에서 JSON을 찾지 못했어요.')
    raw = json.loads(match.group(0))
    scene = str(raw.get('scene') or '').strip()[:40] or None
    tags = [str(tag).strip()[:30] for tag in raw.get('tags') or [] if str(tag).strip()][:5]
    try:
        people = max(0, min(500, int(raw.get('people_count') or 0)))
    except (TypeError, ValueError):
        people = 0
    return {'scene': scene, 'tags': tags, 'people_count': people}


def post_result(payload: dict, attempts: int = 5):
    """사진 DB 커밋보다 S3 이벤트가 먼저 올 수 있어 404는 잠시 뒤 다시 보낸다."""
    request_body = json.dumps(payload).encode()
    for attempt in range(attempts):
        request = urllib.request.Request(os.environ['RESULT_URL'], data=request_body, method='POST', headers={
            'content-type': 'application/json', 'X-Internal-Token': os.environ['INTERNAL_API_TOKEN']})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 422) or attempt == attempts - 1:
                raise
            log.info('Result API %s, retry %s', exc.code, attempt + 1)
        except urllib.error.URLError:
            if attempt == attempts - 1:
                raise
        time.sleep(2 ** attempt)


def handle_record(record: dict):
    bucket = record['s3']['bucket']['name']
    key = urllib.parse.unquote_plus(record['s3']['object']['key'])
    if not DISPLAY_KEY.fullmatch(key):
        log.info('Skip %s', key)
        return
    started = time.monotonic()
    payload = {'key': key}
    try:
        image = s3.get_object(Bucket=bucket, Key=key)['Body'].read()
        payload |= claude_classify(image)
    except Exception as exc:  # 분석 실패도 결과로 보내 화면에 '실패'로 남긴다.
        log.exception('Analysis failed for %s', key)
        payload['error'] = f'CLAUDE_ANALYSIS_FAILED: {type(exc).__name__}'
    payload['elapsed_ms'] = round((time.monotonic() - started) * 1000)
    result = post_result(payload)
    log.info('Saved %s -> %s', key, result)


def lambda_handler(event, context):
    for record in event.get('Records', []):
        handle_record(record)
    return {'ok': True}
