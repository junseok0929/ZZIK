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
    raise NotImplementedError("ZZIK_STARTER:face-grouping:collection_id")


def group_photo(db, photo, data: bytes) -> dict:
    raise NotImplementedError("ZZIK_STARTER:face-grouping:group_photo")



def sync_group_people(db, photo_ids, *, force_review=False):
    """Reconcile group-derived links without undoing independent manual edits.

    API callers flush group split/merge/relink mutations before invoking this.
    """
    raise NotImplementedError("ZZIK_STARTER:face-grouping:sync_group_people")


def cleanup_external(key: str):
    """Outbox consumer; keys are queued with ordinary durable file cleanup rows."""
    raise NotImplementedError("ZZIK_STARTER:face-grouping:cleanup_external")
