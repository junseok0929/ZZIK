"""Transactional upload staging, file cleanup, and failed-analysis requeue."""
from __future__ import annotations

from . import storage as storage_backend
from .image_service import inspect_image, prepare_image, render_cache_key, thumbnail_image
from .models import AnalysisJob, FileCleanup, GroupFace, Photo, Version, now, uid
from .services import drain_cleanup, fail, membership, queue_photo_files
from datetime import timedelta
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


def queue_all_photo_files(db,p):
    queue_photo_files(db,p)
    for face in db.scalars(select(GroupFace).where(GroupFace.photo_id==p.id)):
        db.add(FileCleanup(key=f'rekognition-face:{p.album_id}:{face.external_face_id}'))
    for v in db.scalars(select(Version).where(Version.photo_id==p.id)):
        for size in (None,1600): db.add(FileCleanup(key=render_cache_key(p.original_hash,v.brightness,v.saturation,size)))


def upload_photo(db,album_id,user,data,filename,content_type,request_id):
    raise NotImplementedError("ZZIK_STARTER:upload-jobs:upload_photo")


def queue_failed_analysis(db, photo):
    """Caller holds album and photo locks; never steal a live worker lease."""
    raise NotImplementedError("ZZIK_STARTER:upload-jobs:queue_failed_analysis")
