"""A single original-based, orientation-normalized sRGB rendering pipeline."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageCms, ImageEnhance, ImageOps
from .config import settings

RENDERER_VERSION = "pillow-v1"
MAX_UPLOAD_BYTES = settings.max_upload_bytes
MAX_IMAGE_PIXELS = settings.max_image_pixels
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
SRGB_BYTES = SRGB.tobytes()


class ImageError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _open(data: bytes) -> Image.Image:
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ImageError("IMAGE_SIZE_LIMIT", f"사진은 {MAX_UPLOAD_BYTES // 1024 // 1024}MB 이하로 올려 주세요.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(data))
            if image.format not in {"JPEG", "PNG"}:
                raise ImageError("UNSUPPORTED_IMAGE", "JPEG와 PNG 사진을 지원해요. HEIC는 JPEG로 변환해 주세요.")
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ImageError("IMAGE_PIXEL_LIMIT", "사진의 픽셀 수가 너무 많아요.")
            image.verify()
            image = Image.open(io.BytesIO(data))
            image.load()
            return image
    except ImageError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageError("IMAGE_PIXEL_LIMIT", "사진의 픽셀 수가 너무 많아요.") from exc
    except Exception as exc:
        raise ImageError("INVALID_IMAGE", "사진 파일을 읽을 수 없어요. 정상적인 JPEG 또는 PNG 파일을 올려 주세요.") from exc


def _metadata(image: Image.Image) -> dict:
    result = {"captured_at": None, "capture_timezone": None, "latitude": None, "longitude": None}
    try:
        exif = image.getexif()
        exif_ifd = exif.get_ifd(34665) if 34665 in exif else {}
        captured = exif_ifd.get(36867) or exif.get(36867) or exif.get(306)
        offset = exif_ifd.get(36881) or exif.get(36881)
        if captured:
            dt = datetime.strptime(str(captured).strip("\x00"), "%Y:%m:%d %H:%M:%S")
            if offset and re.fullmatch(r"[+-]\d{2}:\d{2}", str(offset)):
                hours, minutes = map(int, str(offset)[1:].split(":"))
                if hours <= 23 and minutes <= 59:
                    sign = 1 if str(offset)[0] == "+" else -1
                    dt = dt.replace(tzinfo=timezone(sign * timedelta(hours=hours, minutes=minutes)))
                    result["capture_timezone"] = str(offset)
            result["captured_at"] = dt.isoformat()
    except (ValueError, TypeError, KeyError, OSError, SyntaxError):
        pass
    try:
        gps = image.getexif().get_ifd(34853)
        def coordinate(values, ref, positive):
            degrees, minutes, seconds = (float(x) for x in values)
            value = degrees + minutes / 60 + seconds / 3600
            return value if str(ref).upper() == positive else -value
        if gps.get(2) and gps.get(4):
            lat = coordinate(gps[2], gps.get(1), "N")
            lon = coordinate(gps[4], gps.get(3), "E")
            if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
                result.update(latitude=lat, longitude=lon)
    except (ValueError, TypeError, KeyError, ZeroDivisionError, OSError, SyntaxError):
        pass
    return result


def inspect_image(data: bytes, content_type: str | None = None) -> dict:
    image = _open(data)
    mime = "image/jpeg" if image.format == "JPEG" else "image/png"
    declared = (content_type or "").partition(";")[0].lower().strip()
    if declared and declared not in {mime, "application/octet-stream"}:
        raise ImageError("IMAGE_MIME_MISMATCH", "파일 형식과 실제 사진 형식이 달라요.")
    oriented = ImageOps.exif_transpose(image)
    return {"width": oriented.width, "height": oriented.height, "mime": mime,
            "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
            "original_width": image.width, "original_height": image.height,
            "orientation": image.getexif().get(274, 1), **_metadata(image)}


def normalized_image(data: bytes) -> Image.Image:
    image = ImageOps.exif_transpose(_open(data))
    icc = image.info.get("icc_profile")
    if icc:
        try:
            source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            # Preserve alpha independently when converting RGB-compatible profiles.
            alpha = image.getchannel("A") if "A" in image.getbands() else None
            image = ImageCms.profileToProfile(image.convert("RGB") if alpha else image,
                                              source, SRGB, outputMode="RGB")
            if alpha is not None:
                background = Image.new("RGB", image.size, "white")
                background.paste(image, mask=alpha)
                image = background
        except (OSError, ValueError, ImageCms.PyCMSError) as exc:
            raise ImageError("INVALID_COLOR_PROFILE", "사진의 색상 프로필을 읽을 수 없어요. sRGB로 변환해 주세요.") from exc
    elif "A" in image.getbands() or image.mode == "P":
        rgba = image.convert("RGBA")
        background = Image.new("RGB", image.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        image = background
    else:
        image = image.convert("RGB")
    return image


def _settings(brightness: float, saturation: float) -> tuple[float, float]:
    try:
        b, s = float(brightness), float(saturation)
    except (TypeError, ValueError) as exc:
        raise ImageError("INVALID_EDIT_SETTINGS", "보정 설정값을 확인해 주세요.") from exc
    if not math.isfinite(b) or not math.isfinite(s) or not .25 <= b <= 2 or not 0 <= s <= 2:
        raise ImageError("INVALID_EDIT_SETTINGS", "밝기는 0.25–2, 채도는 0–2 사이여야 해요.")
    return b, s


def _jpeg(image: Image.Image, quality: int = 92) -> bytes:
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=quality, subsampling=0,
               optimize=True, icc_profile=SRGB_BYTES)
    return output.getvalue()


def render_image(data: bytes, brightness: float = 1, saturation: float = 1,
                 max_size: int | None = None) -> bytes:
    b, s = _settings(brightness, saturation)
    image = normalized_image(data)
    # Always brightness then saturation on the original; resize only afterwards.
    image = ImageEnhance.Brightness(image).enhance(b)
    image = ImageEnhance.Color(image).enhance(s)
    if max_size:
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    return _jpeg(image)


def prepare_image(data: bytes, max_size: int = 1600) -> bytes:
    result = render_image(data, max_size=max_size)
    if len(result) > 5 * 1024 * 1024:
        result = render_image(data, max_size=1200)
    return result


def thumbnail_image(data: bytes) -> bytes:
    return render_image(data, max_size=480)


def render_cache_key(original_hash: str, brightness: float, saturation: float,
                     max_size: int | None = None) -> str:
    b, s = _settings(brightness, saturation)
    payload = json.dumps({"original": original_hash, "brightness": b, "saturation": s,
                          "renderer": RENDERER_VERSION, "format": "jpeg", "size": max_size}, sort_keys=True)
    return "renders/" + hashlib.sha256(payload.encode()).hexdigest() + ".jpg"


def quality_metrics(data: bytes) -> dict:
    image = normalized_image(data).convert("L")
    # Same exact 384x384 preprocessing for every candidate; these are comparative signals.
    gray = ImageOps.fit(image, (384, 384), method=Image.Resampling.LANCZOS)
    pixels = list(gray.get_flattened_data() if hasattr(gray, "get_flattened_data") else gray.getdata())
    width = 384
    laplacian = [pixels[i - width] + pixels[i + width] + pixels[i - 1] + pixels[i + 1] - 4 * pixels[i]
                 for y in range(1, 383) for x in range(1, 383) for i in [y * width + x]]
    mean = sum(laplacian) / len(laplacian)
    variance = sum((value - mean) ** 2 for value in laplacian) / len(laplacian)
    tiny_image = image.resize((9, 8), Image.Resampling.LANCZOS)
    tiny = list(tiny_image.get_flattened_data() if hasattr(tiny_image, "get_flattened_data") else tiny_image.getdata())
    dhash = 0
    for y in range(8):
        for x in range(8):
            dhash = (dhash << 1) | int(tiny[y * 9 + x] > tiny[y * 9 + x + 1])
    clipped = sum(value <= 8 or value >= 247 for value in pixels) / len(pixels)
    return {"perceptual_hash": f"{dhash:016x}", "sharpness": round(variance, 3),
            "exposure": round(sum(pixels) / len(pixels) / 255, 5),
            "clipped_fraction": round(clipped, 5), "preprocessing": "gray-center-fit-384-v1"}


def best_shot_score(quality: dict | None, faces: list | None = None) -> float | None:
    """A comparative 0–1 signal from stored metrics, not an absolute quality guarantee.

    Only metrics produced by the identical `quality_metrics` preprocessing are combined,
    so two photos are comparable exactly when both were measured the same way.
    """
    if not quality or quality.get("preprocessing") != "gray-center-fit-384-v1":
        return None
    sharpness = quality.get("sharpness")
    exposure = quality.get("exposure")
    clipped = quality.get("clipped_fraction")
    if sharpness is None or exposure is None or clipped is None:
        return None
    # Laplacian variance spans orders of magnitude; compress it before weighting.
    sharp = min(1.0, math.log10(1 + max(0.0, float(sharpness))) / 3)
    clip = max(0.0, 1 - min(1.0, float(clipped) * 10))
    middle = 1 - min(1.0, abs(float(exposure) - .5) * 2.5)
    faces = faces or []
    closed = sum(face.get("eyes_open") is False for face in faces)
    # Without eye data the term stays neutral instead of inventing a penalty or bonus.
    eyes = 1.0 if not faces or all(face.get("eyes_open") is None for face in faces) else max(0.0, 1 - closed / len(faces))
    return round(.4 * sharp + .2 * clip + .2 * middle + .2 * eyes, 4)


def similar_groups(photos: list[dict]) -> list[dict]:
    """Complete-link grouping avoids a weak chain merging different moments."""
    def close(a, b):
        aq, bq = a.get("quality") or {}, b.get("quality") or {}
        ah, bh = aq.get("perceptual_hash"), bq.get("perceptual_hash")
        if not ah or not bh:
            return False
        distance = (int(ah, 16) ^ int(bh, 16)).bit_count()
        ad, bd = a.get("captured_at"), b.get("captured_at")
        if not ad or not bd:
            return a.get("sha256") is not None and a.get("sha256") == b.get("sha256")
        try:
            delta = abs((datetime.fromisoformat(str(ad)) - datetime.fromisoformat(str(bd))).total_seconds())
        except (ValueError, TypeError):
            return False
        return delta <= 120 and distance <= 6
    groups: list[list[dict]] = []
    for photo in photos:
        group = next((g for g in groups if all(close(photo, member) for member in g)), None)
        if group is None:
            groups.append([photo])
        else:
            group.append(photo)
    results = []
    for group in groups:
        if len(group) < 2:
            continue
        def ranking(photo):
            quality = photo.get("quality") or {}
            faces = photo.get("faces") or []
            closed = sum(face.get("eyes_open") is False for face in faces)
            return (closed, quality.get("clipped_fraction", 1), -quality.get("sharpness", 0))
        ordered = sorted(group, key=ranking)
        recommended = ordered[:min(3, max(1, len(ordered) // 2))]
        reasons = {}
        for photo in recommended:
            q = photo.get("quality") or {}
            reasons[photo["id"]] = []
            if q.get("sharpness", 0) >= max((p.get("quality") or {}).get("sharpness", 0) for p in group):
                reasons[photo["id"]].append("비슷한 사진 중 덜 흔들림")
            if q.get("clipped_fraction", 1) <= min((p.get("quality") or {}).get("clipped_fraction", 1) for p in group):
                reasons[photo["id"]].append("밝거나 어둡게 뭉개진 부분이 적음")
            if any(f.get("eyes_open") is False for p in group for f in p.get("faces", [])) and not any(f.get("eyes_open") is False for f in photo.get("faces", [])):
                reasons[photo["id"]].append("눈 감은 사람이 적음")
        results.append({"id": hashlib.sha256("|".join(sorted(p["id"] for p in group)).encode()).hexdigest()[:16],
                        "photos": group, "recommended_ids": [p["id"] for p in recommended], "reasons": reasons})
    return results
