"""Album membership, invitation, settings, and deletion endpoints."""
from __future__ import annotations

from .. import responses as out

import secrets
from ..config import settings
from ..db import get_db
from ..dependencies import auth
from ..models import Album, AlbumMember, ApprovalTarget, FaceGroup, FileCleanup, Notification, Person, Photo, Version
from ..photo_operations import queue_all_photo_files
from ..schemas import AlbumCreate, AlbumPatch, Join
from ..services import album_dict, drain_cleanup, fail, invalidate_photo_reviews, membership, notify_after_commit
from fastapi import APIRouter, Depends
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session as DBSession
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

router = APIRouter()


def timezone_name(name):
    raise NotImplementedError("ZZIK_STARTER:api-albums:timezone_name")


@router.get('/api/albums', response_model=out.PageResponse[out.AlbumResponse], response_model_exclude_unset=True)
def albums(user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-albums:albums")


@router.post('/api/albums',status_code=201, response_model=out.AlbumResponse, response_model_exclude_unset=True)
def create_album(body:AlbumCreate,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-albums:create_album")


@router.post('/api/albums/join', response_model=out.AlbumResponse, response_model_exclude_unset=True)
def join_album(body:Join,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-albums:join_album")


@router.get('/api/albums/{album_id}', response_model=out.AlbumResponse, response_model_exclude_unset=True)
def album_detail(album_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-albums:album_detail")


@router.patch('/api/albums/{album_id}', response_model=out.AlbumResponse, response_model_exclude_unset=True)
def album_patch(album_id:str,body:AlbumPatch,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-albums:album_patch")


@router.post('/api/albums/{album_id}/invite', response_model=out.InviteResponse, response_model_exclude_unset=True)
def rotate_invite(album_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-albums:rotate_invite")


@router.delete('/api/albums/{album_id}', response_model=out.OkResponse, response_model_exclude_unset=True)
def delete_album(album_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-albums:delete_album")


@router.delete('/api/albums/{album_id}/members/{user_id}', response_model=out.OkResponse, response_model_exclude_unset=True)
def remove_member(album_id:str,user_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-albums:remove_member")
