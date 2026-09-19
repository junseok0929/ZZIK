"""Explicit fixture and AWS face analysis; never fall back between providers."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from .config import settings
from .image_service import prepare_image, inspect_image


class AnalysisError(ValueError):
    def __init__(self, code: str, message: str, *, retryable: bool = False, calls: int = 0):
        super().__init__(message)
        self.code, self.message, self.retryable, self.calls = code, message, retryable, calls


def fixture_entry(data: bytes, original_hash: str | None = None) -> dict:
    actual = hashlib.sha256(data).hexdigest()
    if original_hash and actual != original_hash:
        raise AnalysisError('IMAGE_HASH_MISMATCH', '저장된 원본의 해시가 달라요. 파일을 확인해 주세요.')
    try:
        manifest = json.loads(Path(settings.fixture_manifest).read_text())
        entry = manifest['fixtures'].get(actual)
    except (OSError, ValueError, KeyError) as exc:
        raise AnalysisError('FIXTURE_UNAVAILABLE', '샘플 분석 파일을 읽을 수 없어요.') from exc
    if entry is None:
        raise AnalysisError('REAL_ANALYSIS_REQUIRED', '실제 분석 연결 필요: 이 사진은 지정된 샘플이 아니에요.')
    return entry


def rekognition_client():
    import boto3
    from botocore.config import Config
    return boto3.client('rekognition', region_name=settings.aws_region,
                        config=Config(connect_timeout=min(5, settings.aws_timeout_seconds),
                                      read_timeout=settings.aws_timeout_seconds,
                                      retries={'mode': 'standard', 'total_max_attempts': 1}))


def aws_error(exc: Exception, calls: int = 0) -> AnalysisError:
    code = getattr(exc, 'response', {}).get('Error', {}).get('Code', type(exc).__name__)
    transient = code in {'InternalServerError', 'ThrottlingException', 'ProvisionedThroughputExceededException',
                         'EndpointConnectionError', 'ReadTimeoutError', 'ConnectTimeoutError', 'ConnectionClosedError'}
    if code in {'NoCredentialsError', 'PartialCredentialsError', 'AccessDeniedException', 'UnrecognizedClientException', 'InvalidSignatureException', 'ExpiredTokenException'}:
        message = 'AWS 분석 인증 또는 권한을 확인해 주세요.'
    else:
        message = 'AWS 사진 분석에 실패했어요. 연결 설정을 확인한 뒤 다시 시도해 주세요.'
    return AnalysisError('AWS_' + code, message, retryable=transient, calls=calls)


def analysis_bytes(data: bytes) -> bytes:
    prepared = prepare_image(data)
    info = inspect_image(prepared)
    if min(info['width'], info['height']) < 80:
        raise AnalysisError('IMAGE_TOO_SMALL', '실제 분석 사진의 가로와 세로는 각각 80픽셀 이상이어야 해요.')
    if len(prepared) > 5 * 1024 * 1024:
        raise AnalysisError('ANALYSIS_IMAGE_TOO_LARGE', '분석용 사진이 AWS의 5MB 제한을 초과했어요.')
    return prepared


def box_dict(box):
    return {key: float(box.get(key.title(), box.get(key, 0))) for key in ('left', 'top', 'width', 'height')}


def box_iou(a, b):
    left, top = max(a['left'], b['left']), max(a['top'], b['top'])
    right = min(a['left'] + a['width'], b['left'] + b['width'])
    bottom = min(a['top'] + a['height'], b['top'] + b['height'])
    intersection = max(0, right - left) * max(0, bottom - top)
    union = a['width'] * a['height'] + b['width'] * b['height'] - intersection
    return intersection / union if union > 0 else 0


def validate_reference(data: bytes, original_hash: str | None = None) -> dict:
    provider = settings.face_analysis_provider
    if provider == 'fixture':
        entry = fixture_entry(data, original_hash)
        faces = entry['faces']
        result = {'provider': 'fixture', 'mode': 'sample', 'model': 'fixture-v1', 'calls': 0}
    elif provider == 'rekognition':
        try:
            response = rekognition_client().detect_faces(Image={'Bytes': analysis_bytes(data)}, Attributes=['DEFAULT'])
            faces = response.get('FaceDetails', [])
        except AnalysisError:
            raise
        except Exception as exc:
            raise aws_error(exc, 1) from exc
        result = {'provider': 'rekognition', 'mode': 'live', 'model': 'rekognition-2016-06-27', 'calls': 1}
    else:
        raise AnalysisError('INVALID_PROVIDER', '분석 제공자 설정을 확인해 주세요.')
    if not faces:
        raise AnalysisError('NO_FACE', '기준 사진에서 얼굴을 찾지 못했어요. 얼굴이 선명한 사진을 골라 주세요.')
    if len(faces) > 1:
        raise AnalysisError('MULTIPLE_FACES', '기준 사진에는 한 사람의 얼굴만 있어야 해요.')
    return dict(result, face_count=1)


# Rekognition general labels mapped to the Korean scene tags the UI filters on. Labels
# outside this vocabulary stay in analysis_metadata rather than becoming user-facing tags.
LABEL_TAGS = {
    'Sea': '바다', 'Ocean': '바다', 'Beach': '바다', 'Coast': '바다', 'Shoreline': '바다',
    'Water': '물', 'Lake': '물', 'River': '물', 'Waterfall': '물', 'Swimming Pool': '물',
    'Mountain': '산', 'Mountain Range': '산', 'Hill': '산', 'Cliff': '산', 'Valley': '산',
    'Food': '음식', 'Meal': '음식', 'Dish': '음식', 'Dessert': '음식', 'Bread': '음식',
    'Seafood': '음식', 'Noodle': '음식', 'Fruit': '음식', 'Drink': '음료', 'Beverage': '음료',
    'Coffee': '카페', 'Coffee Cup': '카페', 'Cafe': '카페', 'Coffee Shop': '카페', 'Cafeteria': '카페',
    'Restaurant': '식당', 'Bar': '식당', 'Dining Table': '식당',
    'Night': '야경', 'Nightlife': '야경', 'Moon': '야경', 'Lighting': '야경',
    'Sunset': '노을', 'Sunrise': '노을', 'Dusk': '노을', 'Dawn': '노을', 'Sky': '하늘', 'Cloud': '하늘',
    'Flower': '꽃', 'Blossom': '꽃', 'Cherry Blossom': '꽃', 'Plant': '자연', 'Tree': '자연',
    'Nature': '자연', 'Grass': '자연', 'Field': '자연', 'Garden': '자연', 'Forest': '숲', 'Woodland': '숲',
    'Jungle': '숲', 'Snow': '눈', 'Ice': '눈', 'Winter': '눈', 'Rain': '비', 'Storm': '비', 'Fog': '비',
    'City': '도시', 'Urban': '도시', 'Town': '도시', 'Downtown': '도시', 'Metropolis': '도시',
    'Building': '건물', 'Architecture': '건물', 'House': '건물', 'Hotel': '건물', 'Tower': '건물',
    'Bridge': '건물', 'Temple': '문화재', 'Shrine': '문화재', 'Palace': '문화재', 'Castle': '문화재',
    'Museum': '문화재', 'Monument': '문화재', 'Church': '문화재',
    'Road': '거리', 'Street': '거리', 'Alley': '거리', 'Path': '거리', 'Sidewalk': '거리',
    'Market': '시장', 'Shop': '시장', 'Bazaar': '시장',
    'Park': '공원', 'Playground': '공원', 'Amusement Park': '공원',
    'Boat': '이동', 'Ship': '이동', 'Airplane': '이동', 'Airport': '이동', 'Train': '이동',
    'Train Station': '이동', 'Car': '이동', 'Bicycle': '이동', 'Bus': '이동',
    'Animal': '동물', 'Pet': '동물', 'Dog': '동물', 'Cat': '동물', 'Bird': '동물',
    'Indoors': '실내', 'Room': '실내', 'Living Room': '실내', 'Bedroom': '실내',
    'Outdoors': '야외', 'Camping': '야외', 'Tent': '야외', 'Hiking': '야외',
    'Selfie': '셀피', 'Portrait': '인물', 'Face': '인물', 'Head': '인물',
    'Party': '모임', 'Festival': '모임', 'Crowd': '모임', 'Wedding': '모임',
}
SCENE_TAGS = sorted(set(LABEL_TAGS.values()))


def analyze(data: bytes, references: list[dict] | None = None, original_hash: str | None = None,
            album_id: str | None = None) -> dict:
    started = time.monotonic()
    references = references or []
    provider = settings.face_analysis_provider
    if provider == 'fixture':
        entry = fixture_entry(data, original_hash)
        identities = {}
        for reference in references:
            try:
                reference_entry = fixture_entry(reference['data'])
            except AnalysisError:
                continue
            identity = reference_entry.get('reference_name')
            if identity:
                identities.setdefault(identity, []).append(reference['id'])
        faces = []
        for face in entry['faces']:
            matches = identities.get(face.get('person_name'), [])
            person_id = matches[0] if len(matches) == 1 else None
            faces.append({'box': dict(face['box']), 'person_id': person_id,
                          'similarity': face.get('similarity') if person_id else None,
                          'eyes_open': face.get('eyes_open'), 'sample': True})
        result = {'faces': faces, 'tags': list(entry.get('tags', [])), 'provider': 'fixture',
                  'mode': 'sample', 'model': 'fixture-v1', 'calls': 0,
                  'metadata': {'notice': '지정된 파일 해시에 연결된 샘플 결과이며 실제 AI 분석이 아니에요.'}}
    elif provider == 'rekognition':
        result = _analyze_aws(data, references)
    else:
        raise AnalysisError('INVALID_PROVIDER', '분석 제공자 설정을 확인해 주세요.')
    return dict(result, face_count=len(result['faces']),
                unknown_faces=sum(face['person_id'] is None for face in result['faces']),
                elapsed_ms=round((time.monotonic() - started) * 1000))


def _analyze_aws(data, references):
    client = rekognition_client()
    image = analysis_bytes(data)
    calls = 0
    def call(method, **kwargs):
        nonlocal calls
        calls += 1
        try:
            return getattr(client, method)(**kwargs)
        except Exception as exc:
            raise aws_error(exc, calls) from exc
    detected = call('detect_faces', Image={'Bytes': image}, Attributes=['ALL'])
    faces = []
    candidates = []
    for face in detected.get('FaceDetails', []):
        eyes = face.get('EyesOpen', {})
        faces.append({'box': box_dict(face['BoundingBox']), 'person_id': None, 'similarity': None,
                      'detection_confidence': face.get('Confidence'),
                      'eyes_open': eyes.get('Value') if eyes.get('Confidence', 0) >= 90 else None})
        candidates.append({})
    # Detect first, as CompareFaces raises for an image without a detectable face.
    if faces:
        for reference in references:
            if not reference.get('data'):
                continue
            response = call('compare_faces', SourceImage={'Bytes': analysis_bytes(reference['data'])},
                            TargetImage={'Bytes': image},
                            SimilarityThreshold=max(0, settings.rekognition_similarity_threshold - settings.rekognition_candidate_margin),
                            QualityFilter='AUTO')
            for match in response.get('FaceMatches', []):
                box = box_dict(match['Face']['BoundingBox'])
                overlaps = [(box_iou(box, face['box']), i) for i, face in enumerate(faces)]
                overlap, index = max(overlaps)
                if overlap >= .4:
                    person = reference['id']
                    candidates[index][person] = max(float(match['Similarity']), candidates[index].get(person, 0))
        for face, scores in zip(faces, candidates):
            ordered = sorted(scores.items(), key=lambda row: row[1], reverse=True)
            if not ordered:
                continue
            person, score = ordered[0]
            if score >= settings.rekognition_similarity_threshold and (len(ordered) == 1 or score - ordered[1][1] >= settings.rekognition_candidate_margin):
                face.update(person_id=person, similarity=score)
            else:
                face['uncertain'] = True
        # A person may appear twice via a mirror; ambiguous competing face assignments
        # are left for human confirmation instead of silently adding more people.
    labels = call('detect_labels', Image={'Bytes': image}, MaxLabels=30, MinConfidence=80,
                  Features=['GENERAL_LABELS'])
    tag_set = {LABEL_TAGS[label['Name']] for label in labels.get('Labels', []) if label['Name'] in LABEL_TAGS}
    return {'faces': faces, 'tags': sorted(tag_set), 'provider': 'rekognition', 'mode': 'live',
            'model': 'rekognition-2016-06-27', 'calls': calls,
            'metadata': {'labels': [{'name': item['Name'], 'confidence': item['Confidence']} for item in labels.get('Labels', [])],
                         'label_model': labels.get('LabelModelVersion'), 'region': settings.aws_region,
                         'similarity_threshold': settings.rekognition_similarity_threshold,
                         'candidate_margin': settings.rekognition_candidate_margin,
                         'coordinate_system': 'EXIF-normalized-image-relative',
                         'matching': 'registered-reference-compare-faces'}}
