"""Photo upload, filtering, metadata, manual people, and downloads."""
from __future__ import annotations

from .. import responses as out
from fastapi.responses import Response as BinaryResponse

from .. import storage as storage_backend
from ..config import settings
from ..db import get_db
from ..dependencies import auth
from ..media import stored_file, version_file_response
from ..models import Person, Photo, PhotoPerson
from ..photo_operations import queue_all_photo_files, upload_photo
from ..schemas import PeopleSet, PhotoPatch
from ..services import drain_cleanup, fail, get_photo, get_version, invalidate_photo_reviews, membership, photo_dict
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pathlib import Path
from sqlalchemy import Text, and_, func, or_, select
from sqlalchemy.orm import Session as DBSession
from typing import Literal

router = APIRouter()


@router.post('/api/albums/{album_id}/photos',status_code=201, response_model=out.PhotoResponse, response_model_exclude_unset=True)
def upload(album_id:str,file:UploadFile=File(...),request_id:str=Form(...,min_length=8,max_length=100),user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-photos:upload")


@router.get('/api/albums/{album_id}/photos', response_model=out.PhotoListResponse, response_model_exclude_unset=True)
def list_photos(album_id:str,page:int=Query(1,ge=1),page_size:int=Query(40,ge=1,le=100),
                filter:Literal['all','mine','solo','group','no_faces','review','final']='all',people:str='',
                match:Literal['all','any']='all',tag:str='',q:str='',mine:bool=False,sort:Literal['newest','oldest','captured']='newest',date:str='',
                user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-photos:list_photos")


@router.get('/api/photos/{photo_id}', response_model=out.PhotoDetailResponse, response_model_exclude_unset=True)
def photo_detail(photo_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-photos:photo_detail")


@router.patch('/api/photos/{photo_id}', response_model=out.PhotoDetailResponse, response_model_exclude_unset=True)
def patch_photo(photo_id:str,body:PhotoPatch,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-photos:patch_photo")


@router.delete('/api/photos/{photo_id}', response_model=out.OkResponse, response_model_exclude_unset=True)
def delete_photo(photo_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-photos:delete_photo")


@router.put('/api/photos/{photo_id}/people', response_model=out.PhotoDetailResponse, response_model_exclude_unset=True)
def set_people(photo_id:str,body:PeopleSet,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-photos:set_people")


@router.get('/api/photos/{photo_id}/file', response_class=BinaryResponse, responses={200: {'content': {mime: {'schema': {'type': 'string', 'format': 'binary'}} for mime in ('image/jpeg', 'image/png')}}, 307: {'description': 'Redirect to private signed storage URL'}})
def photo_file(photo_id:str,kind:Literal['original','thumbnail','display']='display',download:bool=False,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-photos:photo_file")


@router.get('/api/photos/{photo_id}/download', response_class=BinaryResponse, responses={200: {'content': {mime: {'schema': {'type': 'string', 'format': 'binary'}} for mime in ('image/jpeg', 'image/png')}}, 307: {'description': 'Redirect to private signed storage URL'}})
def photo_download(photo_id:str,version_id:str|None=None,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-photos:photo_download")


@router.get('/api/albums/{album_id}/download', response_class=BinaryResponse, responses={200: {'content': {'application/zip': {'schema': {'type': 'string', 'format': 'binary'}}}}})
def album_download(album_id:str,photo_ids:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    """A spooled ZIP keeps a bounded batch of originals out of browser memory."""
    raise NotImplementedError("ZZIK_STARTER:api-photos:album_download")
