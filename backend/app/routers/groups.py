"""Album-scoped face-group analysis, linking, merging, and splitting."""
from __future__ import annotations

from .. import responses as out

from ..config import settings
from ..db import get_db
from ..dependencies import auth
from ..models import AnalysisJob, FaceGroup, GroupFace, Person, Photo, now
from ..schemas import GroupMerge, GroupPatch, GroupSplit
from ..services import fail, membership
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

router = APIRouter()


def group_dict(db,g):
    raise NotImplementedError("ZZIK_STARTER:api-groups:group_dict")


def get_group(db,group_id,user):
    raise NotImplementedError("ZZIK_STARTER:api-groups:get_group")


@router.get('/api/albums/{album_id}/face-groups', response_model=out.FaceGroupsResponse, response_model_exclude_unset=True)
def face_groups(album_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-groups:face_groups")


@router.post('/api/albums/{album_id}/face-groups/analyze', response_model=out.QueuedResponse, response_model_exclude_unset=True)
def analyze_face_groups(album_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-groups:analyze_face_groups")


def apply_group_person(db,g,person_id):
    raise NotImplementedError("ZZIK_STARTER:api-groups:apply_group_person")


@router.patch('/api/face-groups/{group_id}', response_model=out.FaceGroupResponse, response_model_exclude_unset=True)
def patch_group(group_id:str,body:GroupPatch,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-groups:patch_group")


@router.post('/api/face-groups/merge', response_model=out.FaceGroupResponse, response_model_exclude_unset=True)
def merge_groups(body:GroupMerge,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-groups:merge_groups")


@router.post('/api/face-groups/{group_id}/split',status_code=201, response_model=out.FaceGroupResponse, response_model_exclude_unset=True)
def split_group(group_id:str,body:GroupSplit,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-groups:split_group")
