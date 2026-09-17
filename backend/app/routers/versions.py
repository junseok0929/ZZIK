"""Non-destructive edits, version history, approvals, and final selection."""
from __future__ import annotations

from .. import responses as out
from fastapi.responses import Response as BinaryResponse

from .. import storage as storage_backend
from ..db import get_db
from ..dependencies import auth, ensure_target_member
from ..image_service import render_image
from ..media import version_file_response
from ..models import Approval, ApprovalTarget, Version
from ..schemas import RenderSettings, ReviewRequest, VersionCreate
from ..services import approval_state, effective_people, fail, get_photo, get_version, notify_after_commit, version_dict
from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

router = APIRouter()


@router.get('/api/photos/{photo_id}/versions', response_model=out.ItemsResponse[out.VersionResponse], response_model_exclude_unset=True)
def versions(photo_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-versions:versions")


@router.post('/api/photos/{photo_id}/versions',status_code=201, response_model=out.VersionResponse, response_model_exclude_unset=True)
def create_version(photo_id:str,body:VersionCreate,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-versions:create_version")


@router.post('/api/photos/{photo_id}/preview', response_class=BinaryResponse, responses={200: {'content': {mime: {'schema': {'type': 'string', 'format': 'binary'}} for mime in ('image/jpeg',)}}})
def preview(photo_id:str,body:RenderSettings,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-versions:preview")


@router.get('/api/versions/{version_id}/file', response_class=BinaryResponse, responses={200: {'content': {mime: {'schema': {'type': 'string', 'format': 'binary'}} for mime in ('image/jpeg',)}}, 307: {'description': 'Redirect to private signed storage URL'}})
def version_file(version_id:str,download:bool=False,preview:bool=False,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-versions:version_file")


@router.post('/api/versions/{version_id}/request-review', response_model=out.VersionResponse, response_model_exclude_unset=True)
def request_review(version_id:str,body:ReviewRequest,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-versions:request_review")


@router.post('/api/versions/{version_id}/approval', response_model=out.VersionResponse, response_model_exclude_unset=True)
def approve(version_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-versions:approve")


@router.delete('/api/versions/{version_id}/approval', response_model=out.VersionResponse, response_model_exclude_unset=True)
def revoke_approval(version_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-versions:revoke_approval")


@router.post('/api/versions/{version_id}/final', response_model=out.VersionResponse, response_model_exclude_unset=True)
def set_final(version_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-versions:set_final")
