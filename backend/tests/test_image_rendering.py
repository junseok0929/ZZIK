"""The EXIF/alpha boundaries shared by preview and original-resolution export."""
import hashlib
import io
from PIL import Image, ImageChops, ImageOps, ImageStat
from backend.app.image_service import inspect_image, render_image


def test_exif_rotation_preview_and_export_match_without_mutating_original():
    image=Image.new('RGB',(180,100),(30,90,160))
    image.paste((210,90,40),(0,0,65,100))
    exif=Image.Exif();exif[274]=6;exif[36867]='2026:09:16 08:30:00'
    stream=io.BytesIO();image.save(stream,'JPEG',exif=exif)
    original=stream.getvalue();before=hashlib.sha256(original).hexdigest()
    metadata=inspect_image(original,'image/jpeg')
    assert (metadata['width'],metadata['height'])==(100,180)
    assert metadata['captured_at']=='2026-09-16T08:30:00'
    assert metadata['capture_timezone'] is None
    export=Image.open(io.BytesIO(render_image(original,1.15,.65)))
    preview=Image.open(io.BytesIO(render_image(original,1.15,.65,max_size=90)))
    assert export.size==(100,180) and preview.size==(50,90)
    assert export.getexif().get(274,1)==1
    reduced=export.resize(preview.size,Image.Resampling.LANCZOS)
    assert max(ImageStat.Stat(ImageChops.difference(reduced,preview)).mean)<4
    assert before==hashlib.sha256(original).hexdigest()


def test_transparent_png_is_composited_on_same_white_background_for_export_and_preview():
    image=Image.new('RGBA',(100,80),(0,0,0,0));image.paste((100,150,200,255),(25,20,75,60))
    stream=io.BytesIO();image.save(stream,'PNG');original=stream.getvalue()
    output=render_image(original);preview=render_image(original,max_size=1600)
    assert output==preview
    rendered=Image.open(io.BytesIO(output))
    assert rendered.mode=='RGB' and rendered.size==(100,80)
    assert all(channel>248 for channel in rendered.getpixel((4,4)))
    assert rendered.info.get('icc_profile')
