"""Optional album-isolated Rekognition collection grouping.

Index all detected faces, then search each FaceId. This deliberately avoids the
largest-face-only behavior of SearchFacesByImage. Existing assignments are never
regrouped, so a user's split/merge decisions survive retries.
"""
from __future__ import annotations

import hashlib
import re
from sqlalchemy import select
from .analysis import AnalysisError, analysis_bytes, aws_error, box_dict, box_iou, rekognition_client
from .config import settings
from .models import Album, FaceGroup, GroupFace, Person, Photo, PhotoPerson
from .services import invalidate_photo_reviews


def collection_id(album_id: str) -> str:
    prefix = re.sub(r'[^a-zA-Z0-9_.-]', '-', settings.rekognition_collection_prefix)[:100]
    return prefix + hashlib.sha256(str(album_id).encode()).hexdigest()


def group_photo(db, photo, data: bytes) -> dict:
    if settings.face_analysis_provider != 'rekognition':
        raise AnalysisError('GROUPING_REQUIRES_REKOGNITION', '등록 없는 인물 묶기는 실제 AWS 분석 연결이 필요해요.')
    # Serialize album group assignment, including remote indexing, across workers.
    db.scalar(select(Album).where(Album.id == photo.album_id).with_for_update())
    existing = list(db.scalars(select(GroupFace).where(GroupFace.photo_id == photo.id)))
    if existing:
        sync_group_people(db, [photo.id])
        return {'provider': 'rekognition', 'status': 'preserved', 'face_count': len(existing), 'calls': 0}
    client = rekognition_client()
    collection = collection_id(photo.album_id)
    calls = 0
    def call(method, **kwargs):
        nonlocal calls
        calls += 1
        try:
            return getattr(client, method)(**kwargs)
        except Exception as exc:
            raise aws_error(exc, calls) from exc
    try:
        calls += 1
        client.describe_collection(CollectionId=collection)
    except Exception as exc:
        code = getattr(exc, 'response', {}).get('Error', {}).get('Code')
        if code != 'ResourceNotFoundException':
            raise aws_error(exc, calls) from exc
        try:
            calls += 1
            client.create_collection(CollectionId=collection)
        except Exception as create_exc:
            if getattr(create_exc, 'response', {}).get('Error', {}).get('Code') != 'ResourceAlreadyExistsException':
                raise aws_error(create_exc, calls) from create_exc
    indexed = call('index_faces', CollectionId=collection, Image={'Bytes': analysis_bytes(data)},
                   ExternalImageId=photo.id, MaxFaces=100, QualityFilter='AUTO', DetectionAttributes=['DEFAULT'])
    used_groups = set()
    for record in indexed.get('FaceRecords', []):
        face = record['Face']
        face_id = face['FaceId']
        search = call('search_faces', CollectionId=collection, FaceId=face_id,
                      MaxFaces=100, FaceMatchThreshold=max(0, settings.rekognition_similarity_threshold - settings.rekognition_candidate_margin))
        scores = {}
        for match in search.get('FaceMatches', []):
            match_id = match['Face']['FaceId']
            if match_id == face_id:
                continue
            member = db.scalar(select(GroupFace).join(FaceGroup).where(GroupFace.external_face_id == match_id,
                                                                        FaceGroup.album_id == photo.album_id,
                                                                        GroupFace.photo_id != photo.id))
            if member and member.group_id not in used_groups:
                scores[member.group_id] = max(float(match['Similarity']), scores.get(member.group_id, 0))
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        group = None
        similarity = None
        if ranked:
            group_id, score = ranked[0]
            if score >= settings.rekognition_similarity_threshold and (len(ranked) == 1 or score-ranked[1][1] >= settings.rekognition_candidate_margin):
                group = db.get(FaceGroup, group_id)
                similarity = score
        if group is None:
            group = FaceGroup(album_id=photo.album_id, name='이름 없는 인물')
            db.add(group)
            db.flush()
        used_groups.add(group.id)
        db.add(GroupFace(group_id=group.id, photo_id=photo.id, external_face_id=face_id,
                         box=box_dict(face['BoundingBox']), similarity=similarity))
        db.flush()
    sync_group_people(db, [photo.id])
    return {'provider': 'rekognition', 'status': 'completed', 'face_count': len(indexed.get('FaceRecords', [])),
            'unindexed_faces': len(indexed.get('UnindexedFaces', [])), 'model': indexed.get('FaceModelVersion'),
            'calls': calls, 'method': 'index-all-faces-then-search-each-face', 'collection_id': collection}



def sync_group_people(db, photo_ids, *, force_review=False):
    """Reconcile group-derived links without undoing independent manual edits.

    API callers flush group split/merge/relink mutations before invoking this.
    """
    db.flush()
    for photo in db.scalars(select(Photo).where(Photo.id.in_(set(photo_ids))).order_by(Photo.id).with_for_update()):
        assignments = db.execute(select(GroupFace, FaceGroup).join(FaceGroup)
                                 .where(GroupFace.photo_id == photo.id, FaceGroup.album_id == photo.album_id)).all()
        valid_people = set(db.scalars(select(Person.id).where(Person.album_id == photo.album_id)))
        desired = {group.person_id for _, group in assignments if group.person_id in valid_people}
        links = {link.person_id: link for link in db.scalars(select(PhotoPerson).where(PhotoPerson.photo_id == photo.id))}
        before = {person_id for person_id, link in links.items() if not link.excluded}
        for person_id, link in links.items():
            if link.source == 'group' and not link.excluded and person_id not in desired:
                db.delete(link)
        for person_id in desired:
            if person_id not in links:
                db.add(PhotoPerson(photo_id=photo.id, person_id=person_id, source='group', excluded=False))
        faces = [dict(face) for face in photo.faces]
        for group_face, group in assignments:
            candidates = [(box_iou(face['box'], group_face.box), index) for index, face in enumerate(faces)]
            if not candidates:
                continue
            overlap, index = max(candidates)
            if overlap < .4:
                continue
            face = faces[index]
            # Keep the reference-based result to restore it if the group is unlinked.
            if 'group_id' not in face:
                face['reference_person_id'] = face.get('person_id')
            face['group_id'] = group.id
            face['group_person_id'] = group.person_id if group.person_id in valid_people else None
            face['person_id'] = face['group_person_id'] or face.get('reference_person_id')
        photo.faces = faces
        photo.unknown_faces = sum(face.get('person_id') is None for face in faces)
        db.flush()
        after = set(db.scalars(select(PhotoPerson.person_id).where(PhotoPerson.photo_id == photo.id, PhotoPerson.excluded == False)))
        if before != after or force_review:
            invalidate_photo_reviews(db, photo, '인물 그룹의 연결이 변경되어 다시 확인이 필요해요.')


def cleanup_external(key: str):
    """Outbox consumer; keys are queued with ordinary durable file cleanup rows."""
    client = rekognition_client()
    try:
        if key.startswith('rekognition-face:'):
            _, album_id, face_id = key.split(':', 2)
            client.delete_faces(CollectionId=collection_id(album_id), FaceIds=[face_id])
        elif key.startswith('rekognition-collection:'):
            album_id = key.split(':', 1)[1]
            client.delete_collection(CollectionId=collection_id(album_id))
        else:
            raise ValueError('Unknown Rekognition cleanup key')
    except Exception as exc:
        code = getattr(exc, 'response', {}).get('Error', {}).get('Code')
        if code not in {'ResourceNotFoundException'}:
            raise
