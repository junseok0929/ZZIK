"""Serve protected originals and render cached version downloads."""
from __future__ import annotations

from . import storage as storage_backend
from .config import settings
from .image_service import render_cache_key, render_image
from .services import fail
from fastapi import Response
from fastapi.responses import RedirectResponse
from pathlib import Path
from urllib.parse import quote


def stored_file(key,mime,filename=None):
    storage=storage_backend.get_storage()
    if settings.storage_backend=='s3': return RedirectResponse(storage.signed_url(key,filename=filename),status_code=307)
    try: data=storage.get(key)
    except FileNotFoundError: fail(404,'FILE_NOT_FOUND','파일을 찾을 수 없어요.')
    headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(filename)} if filename else {}
    return Response(data,media_type=mime,headers=headers)


def version_file_response(photo,version,download=False,preview=False):
    raise NotImplementedError("ZZIK_STARTER:version-download:version_file_response")
