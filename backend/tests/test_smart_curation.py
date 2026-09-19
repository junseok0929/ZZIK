"""Smart albums, member labels, the Korean phrase parser and the best-shot score.

The API cases reuse the real PostgreSQL fixture from test_api_integration; the parser
and score cases are pure functions and run without a database.
"""
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from zipfile import ZipFile

from PIL import Image
from sqlalchemy import select

from backend.app import worker
from backend.app.image_service import best_shot_score, quality_metrics
from backend.app.models import Photo
from backend.app.nlsearch import parse_query
from backend.tests.test_api_integration import api, create_version, post_photo, register_people  # noqa: F401

PEOPLE = [{'id': 'p-jisu', 'name': '지수'}, {'id': 'p-minji', 'name': '민지'}]


def textured_png():
    """A patterned image so sharpness is measurably above zero, unlike a flat colour."""
    image = Image.new('RGB', (200, 160))
    image.putdata([((x * 7 + y * 13) % 256, (x * 5) % 256, (y * 11) % 256)
                   for y in range(160) for x in range(200)])
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


# --- Korean phrase parser -----------------------------------------------------

def test_phrase_parser_reads_people_tag_and_group_intent():
    result = parse_query('바다에서 지수랑 민지가 다 나온 단체사진', PEOPLE)
    assert set(result['people']) == {'p-jisu', 'p-minji'}
    assert result['match'] == 'all'
    assert result['tags'] == ['바다']
    assert result['filter'] == 'group'
    # A recognised phrase must not also survive as a plain substring condition.
    assert result['text'] == ''
    assert {chip['kind'] for chip in result['chips']} >= {'person', 'tag', 'filter', 'match'}


def test_phrase_parser_reads_any_match_and_face_counts():
    assert parse_query('지수 또는 민지 사진', PEOPLE)['match'] == 'any'
    assert parse_query('혼자 찍은 사진', PEOPLE)['filter'] == 'solo'
    assert parse_query('3명 나온 사진', PEOPLE).get('face_count') == 3
    # An exact count is not the same condition as "two or more".
    assert parse_query('2명 나온 사진', PEOPLE)['filter'] == ''
    assert parse_query('2명 나온 사진', PEOPLE).get('face_count') == 2


def test_phrase_parser_resolves_absolute_and_relative_dates():
    today = date(2026, 9, 17)
    month = parse_query('2024년 8월 사진', PEOPLE, today=today)
    assert (month['date_from'], month['date_to']) == ('2024-08-01', '2024-08-31')
    assert parse_query('2025-03-04에 찍은 사진', PEOPLE, today=today)['date_from'] == '2025-03-04'
    assert parse_query('작년 사진', PEOPLE, today=today)['date_from'] == '2025-01-01'
    assert parse_query('어제 사진', PEOPLE, today=today)['date_from'] == '2026-09-16'
    assert parse_query('최근 3일 사진', PEOPLE, today=today)['date_from'] == '2026-09-15'
    summer = parse_query('지난여름 바다', PEOPLE, today=today)
    assert (summer['date_from'], summer['date_to']) == ('2025-06-01', '2025-08-31')


def test_phrase_parser_only_matches_this_albums_values():
    assert parse_query('서연 사진', PEOPLE)['people'] == []
    assert parse_query('제주에서 찍은 사진', PEOPLE)['location'] == ''
    known = parse_query('제주에서 찍은 사진', PEOPLE, locations=['제주특별자치도 서귀포시'])
    assert known['location'] == '제주'
    labelled = parse_query('인화 후보만 보여줘', PEOPLE, labels=[{'id': 'l1', 'name': '인화 후보'}])
    assert labelled['label'] == 'l1'


def test_phrase_parser_keeps_unrecognised_words_as_plain_search():
    result = parse_query('한라봉', PEOPLE)
    assert result['text'] == '한라봉'
    assert result['people'] == [] and result['tags'] == [] and result['matched'] is True
    assert parse_query('추천 사진', PEOPLE)['recommended'] is True


# --- Best-shot score ----------------------------------------------------------

def test_best_shot_score_requires_identical_preprocessing():
    assert best_shot_score(None) is None
    assert best_shot_score({'sharpness': 100, 'exposure': .5, 'clipped_fraction': 0}) is None
    assert best_shot_score({'preprocessing': 'gray-center-fit-384-v1', 'sharpness': 100}) is None


def test_best_shot_score_prefers_sharper_and_open_eyes():
    quality = quality_metrics(textured_png())
    assert quality['sharpness'] > 0
    score = best_shot_score(quality, [{'eyes_open': True}])
    assert score is not None and 0 <= score <= 1
    assert best_shot_score(quality, [{'eyes_open': False}]) < score
    # Missing eye data must stay neutral rather than become a penalty.
    assert best_shot_score(quality, [{'eyes_open': None}]) == score
    assert best_shot_score(dict(quality, sharpness=0), [{'eyes_open': True}]) < score


# --- Labels -------------------------------------------------------------------

def album_labels(client, album):
    return client.get(f"/api/albums/{album['id']}/labels").json()


def test_labels_are_album_scoped_and_filter_the_gallery(api):
    owner, member, outsider, album, samples, _, _ = api
    photo = post_photo(owner, album, samples)
    other = post_photo(owner, album, samples, 'landscape')
    created = owner.post(f"/api/albums/{album['id']}/labels", json={'name': '인화 후보', 'color': '#c2410c'})
    assert created.status_code == 201, created.text
    label = created.json()
    assert label['photo_count'] == 0 and label['color'] == '#c2410c'
    assert owner.post(f"/api/albums/{album['id']}/labels", json={'name': '인화 후보'}).status_code == 409
    assert owner.post(f"/api/albums/{album['id']}/labels", json={'name': 'bad', 'color': 'red'}).status_code == 422
    assert outsider.get(f"/api/albums/{album['id']}/labels").status_code == 404

    applied = member.put(f"/api/photos/{photo['id']}/labels", json={'label_ids': [label['id']]})
    assert applied.status_code == 200, applied.text
    assert [item['id'] for item in applied.json()['labels']] == [label['id']]
    assert album_labels(owner, album)['items'][0]['photo_count'] == 1

    filtered = owner.get(f"/api/albums/{album['id']}/photos", params={'label': label['id']}).json()
    assert [item['id'] for item in filtered['items']] == [photo['id']]
    assert owner.get(f"/api/albums/{album['id']}/photos", params={'label': 'missing'}).status_code == 422

    renamed = owner.patch(f"/api/labels/{label['id']}", json={'name': '단톡 공유'})
    assert renamed.status_code == 200 and renamed.json()['name'] == '단톡 공유'
    assert owner.delete(f"/api/labels/{label['id']}").status_code == 200
    assert album_labels(owner, album)['items'] == []
    # Deleting a label removes the link only; both photos survive.
    assert owner.get(f"/api/photos/{photo['id']}").json()['labels'] == []
    assert owner.get(f"/api/photos/{other['id']}").status_code == 200


def test_photo_labels_reject_another_albums_label(api):
    owner, _, _, album, samples, _, _ = api
    photo = post_photo(owner, album, samples)
    second = owner.post('/api/albums', json={'name': 'Another album'}).json()
    foreign = owner.post(f"/api/albums/{second['id']}/labels", json={'name': '다른 앨범'}).json()
    response = owner.put(f"/api/photos/{photo['id']}/labels", json={'label_ids': [foreign['id']]})
    assert response.status_code == 422 and response.json()['code'] == 'INVALID_LABEL'


def test_labels_do_not_disturb_approvals(api):
    owner, _, _, album, samples, _, _ = api
    register_people(api)
    photo = post_photo(owner, album, samples)
    assert worker.process_one()
    version = create_version(owner, photo, 'warm', brightness=1.2, saturation=.9)
    assert owner.post(f"/api/versions/{version['id']}/request-review", json={'confirmed': True}).status_code == 200
    assert owner.post(f"/api/versions/{version['id']}/approval").json()['approval_count'] == 1
    label = owner.post(f"/api/albums/{album['id']}/labels", json={'name': '인화 후보'}).json()
    owner.put(f"/api/photos/{photo['id']}/labels", json={'label_ids': [label['id']]})
    after = owner.get(f"/api/photos/{photo['id']}").json()['versions'][0]
    # Unlike changing who appears, a label is organisational and keeps approvals valid.
    assert after['approval_count'] == 1 and after['review_requested'] and not after['needs_review']


# --- Smart albums -------------------------------------------------------------

def sections(payload):
    return {section['id']: {item['id']: item for item in section['items']} for section in payload['sections']}


def test_smart_albums_enumerate_real_groupings(api):
    owner, _, outsider, album, samples, factory, _ = api
    people = register_people(api)
    group = post_photo(owner, album, samples)
    post_photo(owner, album, samples, 'landscape')
    assert worker.process_one() and worker.process_one()
    with factory() as db:
        db.scalar(select(Photo).where(Photo.id == group['id'])).location_name = '제주특별자치도 서귀포시'
        db.commit()

    payload = owner.get(f"/api/albums/{album['id']}/smart-albums").json()
    found = sections(payload)
    assert payload['total'] == 2 and payload['analyzing'] == 0 and payload['notice'] is None
    assert found['basic']['all']['count'] == 2
    assert found['basic']['group']['count'] == 1
    assert found['basic']['no_faces']['count'] == 1
    assert found['basic']['mine']['count'] == 1
    assert found['basic']['recommended']['count'] == 2
    # No photo has exactly one face here, so no empty card is offered.
    assert 'solo' not in found['basic'] and 'final' not in found['basic']
    for person in people:
        assert found['person'][f"person-{person['id']}"]['count'] == 1
    combo = next(iter(found['combination'].values()))
    assert combo['count'] == 1 and combo['subtitle'] == '앨범 인물 전원'
    assert found['place']['place-제주특별자치도 서귀포시']['count'] == 1
    assert found['tag']['tag-바다']['count'] == 1
    assert outsider.get(f"/api/albums/{album['id']}/smart-albums").status_code == 404

    # Every card must open a filter that returns exactly the photos it counted.
    for section in payload['sections']:
        for card in section['items']:
            result = owner.get(f"/api/albums/{album['id']}/photos", params=card['query'])
            assert result.status_code == 200, (card, result.text)
            assert result.json()['total'] == card['count'], card


def test_smart_albums_report_unfinished_analysis(api):
    owner, _, _, album, samples, _, _ = api
    post_photo(owner, album, samples)
    payload = owner.get(f"/api/albums/{album['id']}/smart-albums").json()
    found = sections(payload)
    assert payload['analyzing'] == 1 and payload['notice']
    # A pending photo counts as an album photo but not yet as a scene or person grouping.
    assert found['basic']['all']['count'] == 1
    assert 'group' not in found['basic'] and 'tag' not in found


# --- Search and filters -------------------------------------------------------

def register_korean_people(api):
    owner, member, _, album, samples, _, _ = api
    names = {'a': '지수', 'b': '민지'}
    for client, kind in ((owner, 'a'), (member, 'b')):
        response = client.post(f"/api/albums/{album['id']}/people",
                               data={'name': names[kind], 'user_id': client.user['id']},
                               files={'file': (kind + '.png', samples[kind], 'image/png')})
        assert response.status_code == 201, response.text


def test_natural_language_search_reports_its_reading(api):
    owner, _, _, album, samples, _, _ = api
    register_korean_people(api)
    group = post_photo(owner, album, samples)
    post_photo(owner, album, samples, 'landscape')
    assert worker.process_one() and worker.process_one()

    result = owner.get(f"/api/albums/{album['id']}/photos",
                       params={'q': '바다에서 지수랑 민지가 다 나온 단체사진', 'nl': 'true'}).json()
    assert [item['id'] for item in result['items']] == [group['id']]
    reading = result['interpretation']
    assert reading['tags'] == ['바다'] and reading['filter'] == 'group' and reading['match'] == 'all'
    assert len(reading['people']) == 2 and reading['chips']

    empty = owner.get(f"/api/albums/{album['id']}/photos", params={'q': '혼자 찍은 사진', 'nl': 'true'}).json()
    assert empty['total'] == 0 and empty['interpretation']['filter'] == 'solo'

    # Without nl the phrase is only a substring search and no reading is claimed.
    plain = owner.get(f"/api/albums/{album['id']}/photos", params={'q': '바다에서 지수랑'}).json()
    assert plain['interpretation'] is None and plain['total'] == 0


def test_explicit_parameters_win_over_the_phrase(api):
    owner, _, _, album, samples, _, _ = api
    group = post_photo(owner, album, samples)
    assert worker.process_one()
    result = owner.get(f"/api/albums/{album['id']}/photos",
                       params={'q': '혼자 찍은 사진', 'nl': 'true', 'filter': 'group'}).json()
    assert [item['id'] for item in result['items']] == [group['id']]


def test_date_range_falls_back_to_upload_time_and_validates_input(api):
    owner, _, _, album, samples, _, _ = api
    photo = post_photo(owner, album, samples)
    today = datetime.now(timezone.utc).date()
    inside = owner.get(f"/api/albums/{album['id']}/photos",
                       params={'date_from': (today - timedelta(days=1)).isoformat(),
                               'date_to': (today + timedelta(days=1)).isoformat()}).json()
    assert [item['id'] for item in inside['items']] == [photo['id']]
    assert owner.get(f"/api/albums/{album['id']}/photos",
                     params={'date_from': '2000-01-01', 'date_to': '2000-12-31'}).json()['total'] == 0
    assert owner.get(f"/api/albums/{album['id']}/photos", params={'date_from': 'yesterday'}).status_code == 422
    reversed_range = owner.get(f"/api/albums/{album['id']}/photos",
                               params={'date_from': '2026-02-02', 'date_to': '2026-01-01'})
    assert reversed_range.status_code == 422 and reversed_range.json()['code'] == 'INVALID_DATE_RANGE'


def test_location_filter_and_best_shot_ordering(api):
    owner, _, _, album, samples, factory, _ = api
    first = post_photo(owner, album, samples, 'group')
    second = post_photo(owner, album, samples, 'landscape')
    assert worker.process_one() and worker.process_one()
    with factory() as db:
        db.scalar(select(Photo).where(Photo.id == first['id'])).location_name = '부산 해운대'
        db.scalar(select(Photo).where(Photo.id == second['id'])).best_shot_score = 0.99
        db.commit()
    located = owner.get(f"/api/albums/{album['id']}/photos", params={'location': '해운대'}).json()
    assert [item['id'] for item in located['items']] == [first['id']]
    ranked = owner.get(f"/api/albums/{album['id']}/photos", params={'sort': 'best'}).json()
    assert ranked['items'][0]['id'] == second['id']
    assert ranked['items'][0]['best_shot_score'] == 0.99
    # The worker stores a score for every analysed photo, so both remain listed.
    assert all(item['best_shot_score'] is not None for item in ranked['items'])


def test_final_zip_exports_the_agreed_version_with_a_manifest(api):
    owner, member, _, album, samples, _, _ = api
    register_people(api)
    edited = post_photo(owner, album, samples, 'group')
    plain = post_photo(owner, album, samples, 'landscape')
    assert worker.process_one() and worker.process_one()
    version = create_version(owner, edited, 'warm', brightness=1.3, saturation=.8)
    assert owner.post(f"/api/versions/{version['id']}/request-review", json={'confirmed': True}).status_code == 200
    owner.post(f"/api/versions/{version['id']}/approval")
    assert member.post(f"/api/versions/{version['id']}/approval").json()['consensus']
    assert owner.post(f"/api/versions/{version['id']}/final").json()['is_final']

    ids = f"{edited['id']},{plain['id']}"
    response = owner.get(f"/api/albums/{album['id']}/download", params={'photo_ids': ids, 'kind': 'final'})
    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as archive:
        names = archive.namelist()
        manifest = archive.read('내용.txt').decode()
    assert any(name.endswith('-final.jpg') for name in names)
    # The photo without an agreed version falls back to its original, and the manifest says so.
    assert sum(name.endswith('.png') for name in names) == 1
    assert '최종본 v1' in manifest and '원본 (최종본 없음)' in manifest

    originals = owner.get(f"/api/albums/{album['id']}/download", params={'photo_ids': ids})
    with ZipFile(BytesIO(originals.content)) as archive:
        assert '내용.txt' not in archive.namelist()
        assert sum(name.endswith('.png') for name in archive.namelist()) == 2
