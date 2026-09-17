import hashlib
import io
import json
from datetime import timedelta

import pytest
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from backend.app import analysis, worker
from backend.app.config import settings
from backend.app.db import Base
from backend.app.image_service import similar_groups
from backend.app.models import Album, AnalysisJob, AnalysisRun, Person, Photo, PhotoPerson, User, now
from backend.app.storage import LocalStorage


def image_bytes(color='blue'):
    out = io.BytesIO()
    Image.new('RGB', (96, 120), color).save(out, format='PNG')
    return out.getvalue()


@pytest.fixture
def fixture_mode(tmp_path, monkeypatch):
    source = image_bytes('green')
    reference = image_bytes('red')
    manifest = {'fixtures': {
        hashlib.sha256(source).hexdigest(): {'faces': [{'person_name': 'member', 'similarity': 99,
                      'box': {'left': .1, 'top': .2, 'width': .3, 'height': .4}}], 'tags': ['바다']},
        hashlib.sha256(reference).hexdigest(): {'faces': [{'person_name': 'member', 'box': {}}],
                                               'reference_name': 'member'},
        hashlib.sha256(image_bytes('white')).hexdigest(): {'faces': [], 'tags': []},
        hashlib.sha256(image_bytes('black')).hexdigest(): {'faces': [{}, {}], 'tags': []},
    }}
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr(settings, 'fixture_manifest', str(path))
    monkeypatch.setattr(settings, 'face_analysis_provider', 'fixture')
    return source, reference


def test_fixture_requires_exact_bytes_and_registered_reference(fixture_mode):
    source, reference = fixture_mode
    result = analysis.analyze(source, [{'id': 'p1', 'name': 'renamed', 'data': reference}])
    assert result['faces'][0]['person_id'] == 'p1'
    assert result['mode'] == 'sample' and result['calls'] == 0
    assert analysis.analyze(source, [])['unknown_faces'] == 1
    with pytest.raises(analysis.AnalysisError, match='실제 분석 연결 필요'):
        analysis.analyze(image_bytes('yellow'))
    with pytest.raises(analysis.AnalysisError) as wrong_hash:
        analysis.analyze(image_bytes('yellow'), original_hash=hashlib.sha256(source).hexdigest())
    assert wrong_hash.value.code == 'IMAGE_HASH_MISMATCH'
    with pytest.raises(analysis.AnalysisError) as no_face:
        analysis.validate_reference(image_bytes('white'))
    assert no_face.value.code == 'NO_FACE'
    with pytest.raises(analysis.AnalysisError) as multi:
        analysis.validate_reference(image_bytes('black'))
    assert multi.value.code == 'MULTIPLE_FACES'


@pytest.fixture
def worker_db(tmp_path, monkeypatch, fixture_mode):
    engine = create_engine(f'sqlite:///{tmp_path}/worker.db', connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(worker, 'SessionLocal', factory)
    storage = LocalStorage(tmp_path / 'files')
    monkeypatch.setattr(worker, 'get_storage', lambda: storage)
    source, reference = fixture_mode
    storage.put('original.png', source)
    storage.put('reference.png', reference)
    with factory() as db:
        db.add(User(id='user', email='test@local', name='Test', password_hash='unused'))
        db.flush()
        db.add(Album(id='album', name='Test', owner_id='user', invite_code='code'))
        db.flush()
        db.add(Person(id='person', album_id='album', name='member', reference_key='reference.png'))
        db.add(Photo(id='photo', album_id='album', uploader_id='user', request_id='upload', filename='photo.png',
                     original_key='original.png', thumbnail_key='thumb.jpg', display_key='display.jpg',
                     original_hash=hashlib.sha256(source).hexdigest(), mime='image/png', width=96, height=120))
        db.flush()
        db.add(AnalysisJob(id='job', photo_id='photo'))
        db.commit()
    yield factory, storage
    engine.dispose()


def test_worker_preserves_manual_exclusion_and_finishes_once(worker_db):
    factory, storage = worker_db
    with factory() as db:
        db.add(PhotoPerson(photo_id='photo', person_id='person', source='manual', excluded=True))
        db.commit()
    assert worker.process_one()
    assert not worker.process_one()
    with factory() as db:
        assert db.get(Photo, 'photo').analysis_status == 'completed'
        assert db.get(Photo, 'photo').face_count == 1
        assert db.get(PhotoPerson, ('photo', 'person')).excluded
        assert len(db.scalars(select(AnalysisRun)).all()) == 1
        assert db.get(AnalysisJob, 'job').attempts == 1
    assert storage.exists('original.png')


def test_dead_worker_lease_recovery_and_old_writer_fencing(worker_db):
    factory, _ = worker_db
    first = worker.claim_job()
    assert first and not worker.claim_job()
    with factory() as db:
        db.get(AnalysisJob, 'job').locked_at = now() - timedelta(seconds=settings.worker_lease_seconds + 10)
        db.commit()
    recovered = worker.claim_job()
    assert recovered and recovered[1] != first[1]
    assert not worker.process_claim(*first)
    assert worker.process_claim(*recovered)
    with factory() as db:
        assert db.get(AnalysisJob, 'job').attempts == 2
        assert db.get(Photo, 'photo').analysis_status == 'completed'
        assert len(db.scalars(select(PhotoPerson)).all()) == 1


def test_unsupported_fixture_fails_without_losing_file(worker_db):
    factory, storage = worker_db
    unsupported = image_bytes('yellow')
    storage.put('original.png', unsupported)
    with factory() as db:
        db.get(Photo, 'photo').original_hash = hashlib.sha256(unsupported).hexdigest()
        db.commit()
    assert worker.process_one()
    with factory() as db:
        assert db.get(AnalysisJob, 'job').status == 'failed'
        assert db.get(AnalysisJob, 'job').attempts == 1
        assert 'REAL_ANALYSIS_REQUIRED' in db.get(Photo, 'photo').analysis_error
        assert not db.scalars(select(PhotoPerson)).all()
    assert storage.get('original.png') == unsupported


def test_live_failure_does_not_use_known_fixture(fixture_mode, monkeypatch):
    from botocore.exceptions import NoCredentialsError
    monkeypatch.setattr(settings, 'face_analysis_provider', 'rekognition')
    class Unavailable:
        def detect_faces(self, **kwargs):
            raise NoCredentialsError()
    monkeypatch.setattr(analysis, 'rekognition_client', lambda: Unavailable())
    with pytest.raises(analysis.AnalysisError) as failure:
        analysis.analyze(fixture_mode[0])
    assert failure.value.code == 'AWS_NoCredentialsError'


def test_similarity_without_capture_time_only_groups_exact_duplicates():
    quality = {'perceptual_hash': 'ffffffffffffffff', 'sharpness': 10, 'clipped_fraction': .2}
    photos = [{'id': 'a', 'sha256': 'original-1', 'quality': quality},
              {'id': 'b', 'sha256': 'original-2', 'quality': quality}]
    assert similar_groups(photos) == []
    photos.append({'id': 'c', 'sha256': 'original-1', 'quality': quality})
    groups = similar_groups(photos)
    assert len(groups) == 1
    assert {photo['id'] for photo in groups[0]['photos']} == {'a', 'c'}


def test_live_matching_uses_each_box_and_leaves_ambiguous_face_unknown(monkeypatch):
    monkeypatch.setattr(settings, 'face_analysis_provider', 'rekognition')
    boxes = [{'Left': .1, 'Top': .2, 'Width': .2, 'Height': .3},
             {'Left': .6, 'Top': .2, 'Width': .2, 'Height': .3}]
    class Client:
        comparisons = 0
        def detect_faces(self, **kwargs):
            return {'FaceDetails': [{'BoundingBox': box, 'EyesOpen': {'Value': True, 'Confidence': 99}} for box in boxes]}
        def compare_faces(self, **kwargs):
            self.comparisons += 1
            scores = [98, 89] if self.comparisons == 1 else [96, 97]
            return {'FaceMatches': [{'Face': {'BoundingBox': box}, 'Similarity': score} for box, score in zip(boxes, scores)]}
        def detect_labels(self, **kwargs):
            return {'Labels': [{'Name': 'Sea', 'Confidence': 98}], 'LabelModelVersion': 'test-model'}
    monkeypatch.setattr(analysis, 'rekognition_client', Client)
    result = analysis.analyze(image_bytes(), [{'id': 'a', 'data': image_bytes('red')}, {'id': 'b', 'data': image_bytes('green')}])
    assert result['unknown_faces'] == 1
    assert result['faces'][0]['person_id'] is None
    assert result['faces'][1]['person_id'] == 'b'
    assert result['calls'] == 4 and result['tags'] == ['바다']


def test_retry_limit_is_durable(worker_db, monkeypatch):
    factory, _ = worker_db
    def failure(*args, **kwargs):
        raise analysis.AnalysisError('AWS_ThrottlingException', '일시 오류', retryable=True, calls=1)
    monkeypatch.setattr(worker, 'analyze', failure)
    for attempt in range(settings.worker_max_attempts):
        with factory() as db:
            db.get(AnalysisJob, 'job').available_at = now() - timedelta(seconds=1)
            db.commit()
        assert worker.process_one()
        with factory() as db:
            assert db.get(AnalysisJob, 'job').attempts == attempt + 1
            assert db.get(AnalysisJob, 'job').status == ('failed' if attempt == settings.worker_max_attempts-1 else 'pending')
    assert not worker.process_one()


def test_grouping_indexes_every_face_and_preserves_existing_assignments(worker_db, monkeypatch):
    from backend.app import grouping
    from backend.app.models import GroupFace
    factory, storage = worker_db
    monkeypatch.setattr(settings, 'face_analysis_provider', 'rekognition')
    class Client:
        searches = []
        def describe_collection(self, **kwargs):
            return {}
        def index_faces(self, **kwargs):
            return {'FaceRecords': [{'Face': {'FaceId': face_id, 'BoundingBox': {'Left': left, 'Top': .1, 'Width': .2, 'Height': .4}}}
                                    for face_id, left in [('face1', .1), ('face2', .6)]], 'FaceModelVersion': '7'}
        def search_faces(self, **kwargs):
            self.searches.append(kwargs['FaceId'])
            return {'FaceMatches': [{'Face': {'FaceId': 'face1'}, 'Similarity': 99}]}
    client = Client()
    monkeypatch.setattr(grouping, 'rekognition_client', lambda: client)
    with factory() as db:
        photo = db.get(Photo, 'photo')
        first = grouping.group_photo(db, photo, storage.get('original.png'))
        db.commit()
        faces = db.scalars(select(GroupFace)).all()
        assert len(faces) == 2 and len({face.group_id for face in faces}) == 2
        assert client.searches == ['face1', 'face2']
        assert first['calls'] == 4
        preserved = grouping.group_photo(db, photo, storage.get('original.png'))
        assert preserved['status'] == 'preserved' and preserved['calls'] == 0
    assert grouping.collection_id('album1') != grouping.collection_id('album2')


def test_group_relink_removes_stale_links_without_overwriting_manual_choices(worker_db):
    from backend.app.grouping import sync_group_people
    from backend.app.models import FaceGroup, GroupFace
    factory, _ = worker_db
    with factory() as db:
        db.add(Person(id='other', album_id='album', name='Another'))
        group = FaceGroup(id='group', album_id='album', person_id='person')
        db.add(group)
        db.flush()
        db.add(GroupFace(group_id='group', photo_id='photo', external_face_id='external', box={'left': .1, 'top': .2, 'width': .3, 'height': .4}))
        sync_group_people(db, ['photo'])
        assert db.get(PhotoPerson, ('photo', 'person')).source == 'group'
        group.person_id = 'other'
        sync_group_people(db, ['photo'])
        assert db.get(PhotoPerson, ('photo', 'person')) is None
        assert db.get(PhotoPerson, ('photo', 'other')).source == 'group'
        # A user explicitly adds one identity and excludes the other.
        db.add(PhotoPerson(photo_id='photo', person_id='person', source='manual', excluded=False))
        other = db.get(PhotoPerson, ('photo', 'other'))
        other.excluded, other.source = True, 'manual'
        group.person_id = None
        sync_group_people(db, ['photo'])
        assert not db.get(PhotoPerson, ('photo', 'person')).excluded
        assert db.get(PhotoPerson, ('photo', 'other')).excluded
