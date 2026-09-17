"""Reference people, account-link acceptance, and reference-image access."""
from __future__ import annotations

from .. import responses as out
from fastapi.responses import Response as BinaryResponse

from .. import storage as storage_backend
from ..config import settings
from ..db import get_db
from ..dependencies import auth, ensure_target_member
from ..image_service import inspect_image
from ..media import stored_file
from ..models import AlbumMember, FileCleanup, Person, Photo, now, uid
from ..schemas import PersonPatch
from ..services import drain_cleanup, fail, invalidate_person_reviews, membership, person_dict
from datetime import timedelta
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

router = APIRouter()


def find_person(db,person_id,user,owner=False):
    raise NotImplementedError("ZZIK_STARTER:api-people:find_person")


@router.get('/api/albums/{album_id}/people', response_model=out.ItemsResponse[out.PersonResponse], response_model_exclude_unset=True)
def list_people(album_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-people:list_people")


@router.post('/api/albums/{album_id}/people',status_code=201, response_model=out.PersonResponse, response_model_exclude_unset=True)
def add_person(album_id:str,name:str=Form(...,min_length=1,max_length=80),file:UploadFile=File(...),user_id:str|None=Form(None),user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-people:add_person")


@router.patch('/api/people/{person_id}', response_model=out.PersonResponse, response_model_exclude_unset=True)
def patch_person(person_id:str,body:PersonPatch,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-people:patch_person")


@router.post('/api/people/{person_id}/accept-link', response_model=out.PersonResponse, response_model_exclude_unset=True)
def accept_person_link(person_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-people:accept_person_link")


@router.delete('/api/people/{person_id}', response_model=out.OkResponse, response_model_exclude_unset=True)
def delete_person(person_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-people:delete_person")


@router.get('/api/people/{person_id}/reference', response_class=BinaryResponse, responses={200: {'content': {mime: {'schema': {'type': 'string', 'format': 'binary'}} for mime in ('image/jpeg', 'image/png')}}, 307: {'description': 'Redirect to private signed storage URL'}})
def person_reference(person_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-people:person_reference")
