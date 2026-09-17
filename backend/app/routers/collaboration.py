"""Version comments, album board, and member notifications."""
from __future__ import annotations

from .. import responses as out

from ..db import get_db
from ..dependencies import auth
from ..models import AlbumMember, Comment, Notification, Photo
from ..schemas import CommentCreate
from ..services import fail, get_version, membership, notify_after_commit, photo_dict, version_dict
from fastapi import APIRouter, Depends
from sqlalchemy import and_, select
from sqlalchemy.orm import Session as DBSession

router = APIRouter()


@router.post('/api/versions/{version_id}/comments',status_code=201, response_model=out.VersionResponse, response_model_exclude_unset=True)
def add_comment(version_id:str,body:CommentCreate,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-collaboration:add_comment")


@router.get('/api/albums/{album_id}/board', response_model=out.BoardResponse, response_model_exclude_unset=True)
def board(album_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-collaboration:board")


@router.get('/api/notifications', response_model=out.ItemsResponse[out.NotificationResponse], response_model_exclude_unset=True)
def notifications(user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-collaboration:notifications")


@router.post('/api/notifications/{notification_id}/read', response_model=out.OkResponse, response_model_exclude_unset=True)
def read_notification(notification_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-collaboration:read_notification")
