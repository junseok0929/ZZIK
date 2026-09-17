"""Explicit fixture and AWS face analysis; never fall back between providers."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from .config import settings
from .image_service import prepare_image, inspect_image


class AnalysisError(ValueError):
    def __init__(self, code: str, message: str, *, retryable: bool = False, calls: int = 0):
        super().__init__(message)
        self.code, self.message, self.retryable, self.calls = code, message, retryable, calls


def fixture_entry(data: bytes, original_hash: str | None = None) -> dict:
    raise NotImplementedError("ZZIK_STARTER:vision:fixture_entry")


def rekognition_client():
    raise NotImplementedError("ZZIK_STARTER:vision:rekognition_client")


def aws_error(exc: Exception, calls: int = 0) -> AnalysisError:
    raise NotImplementedError("ZZIK_STARTER:vision:aws_error")


def analysis_bytes(data: bytes) -> bytes:
    raise NotImplementedError("ZZIK_STARTER:vision:analysis_bytes")


def box_dict(box):
    raise NotImplementedError("ZZIK_STARTER:vision:box_dict")


def box_iou(a, b):
    raise NotImplementedError("ZZIK_STARTER:vision:box_iou")


def validate_reference(data: bytes, original_hash: str | None = None) -> dict:
    raise NotImplementedError("ZZIK_STARTER:vision:validate_reference")


LABEL_TAGS = {'Sea': '바다', 'Ocean': '바다', 'Beach': '바다', 'Mountain': '산', 'Food': '음식',
              'Cafe': '카페', 'Coffee Shop': '카페', 'Night': '야경', 'Sunset': '노을',
              'Flower': '꽃', 'Forest': '숲', 'City': '도시'}


def analyze(data: bytes, references: list[dict] | None = None, original_hash: str | None = None,
            album_id: str | None = None) -> dict:
    raise NotImplementedError("ZZIK_STARTER:vision:analyze")


def _analyze_aws(data, references):
    raise NotImplementedError("ZZIK_STARTER:vision:_analyze_aws")
