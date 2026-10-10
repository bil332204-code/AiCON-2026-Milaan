from io import BytesIO
from pathlib import Path
import hashlib, warnings
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 25_000_000

def clean_image(raw):
    if len(raw) > 10 * 1024 * 1024: raise ValueError("Image exceeds 10 MB")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(BytesIO(raw)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}: raise ValueError("Only JPG, PNG and WEBP are accepted")
                if image.width * image.height > 25_000_000: raise ValueError("Image exceeds 25 megapixels")
                image.load()
                clean = ImageOps.exif_transpose(image).convert("RGB")
                clean.thumbnail((2400, 2400))
                out = BytesIO()
                clean.save(out, "JPEG", quality=92)
                return out.getvalue(), hashlib.sha256(raw).hexdigest()
        except (Image.DecompressionBombError, Image.DecompressionBombWarning, OSError) as exc:
            raise ValueError("Invalid or oversized image") from exc

def image_path(settings, filename):
    if Path(filename).name != filename: raise ValueError("Invalid storage path")
    return settings.storage_dir / filename
