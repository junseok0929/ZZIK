"""Analysis status, retry requests, and similar-photo recommendations."""
from __future__ import annotations

from .. import responses as out

from ..config import settings
from ..db import get_db
from ..dependencies import auth
from ..image_service import similar_groups
from ..models import AnalysisJob, AnalysisRun, Photo
from ..photo_operations import queue_failed_analysis
from ..services import fail, get_photo, membership, photo_dict
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

router = APIRouter()


@router.post('/api/photos/{photo_id}/reanalyze', response_model=out.PhotoResponse, response_model_exclude_unset=True)
def reanalyze(photo_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-analysis:reanalyze")


@router.get('/api/albums/{album_id}/analysis-status', response_model=out.AnalysisStatusResponse, response_model_exclude_unset=True)
def album_analysis_status(album_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-analysis:album_analysis_status")


@router.post('/api/albums/{album_id}/reanalyze-failed', response_model=out.QueuedResponse, response_model_exclude_unset=True)
def reanalyze_album_failures(album_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-analysis:reanalyze_album_failures")


@router.get('/api/albums/{album_id}/recommendations', response_model=out.RecommendationsResponse, response_model_exclude_unset=True)
def recommendations(album_id:str,user=Depends(auth),db:DBSession=Depends(get_db)):
    raise NotImplementedError("ZZIK_STARTER:api-analysis:recommendations")
