"""
Cheap checks on the photo BEFORE we send it to Gemini.

1. Sharpness: a hopelessly blurry photo is rejected right here. That saves a
   Gemini request, and it doesn't rely on the LLM admitting it can't read
   something (in testing, Gemini sometimes "read" invented values from a very
   blurry photo).
2. Shrinking: phone photos are often 4000+ pixels wide. Gemini reads a
   1600-pixel image just as well, and the smaller file uploads faster and uses
   fewer tokens of our free-tier quota.
"""

import io
import logging

from PIL import Image, ImageFilter, ImageOps, ImageStat, UnidentifiedImageError

logger = logging.getLogger("odhu.image")

# Below this, the photo is too blurry to read. Measured on our samples: sharp
# documents score 30-55 and the blurry sample scores about 8. We set it low on
# purpose, so we only reject photos that are clearly hopeless; Gemini's own
# "legibility" answer handles the borderline ones.
MIN_SHARPNESS = 10.0
MAX_SIDE = 1600  # pixels


def sharpness(image: Image.Image) -> float:
    """
    How sharp the photo is. We find the edges (places where brightness changes
    suddenly, like the outline of each letter) and measure how strong they are.
    Blur smooths edges away, so a blurry photo gets a low score.
    """
    gray = image.convert("L")
    gray = gray.resize((1000, max(1, round(gray.height * 1000 / gray.width))))  # same scale for every photo
    edges = gray.filter(ImageFilter.FIND_EDGES)
    return ImageStat.Stat(edges).stddev[0]


def prepare_image(data: bytes, mime_type: str) -> tuple[bytes, str, float | None]:
    """
    Return (image bytes to send, their MIME type, sharpness score).
    If Pillow can't open the image (e.g. HEIC), send the original and return None
    for sharpness, so Gemini decides on its own.
    """
    try:
        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image)  # respect the phone's rotation flag
    except (UnidentifiedImageError, OSError):
        logger.info("could not open %s with Pillow, sending it unchanged", mime_type)
        return data, mime_type, None

    score = sharpness(image)

    if max(image.size) > MAX_SIDE:
        image.thumbnail((MAX_SIDE, MAX_SIDE))  # keeps the aspect ratio
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=85)
        return buffer.getvalue(), "image/jpeg", score

    return data, mime_type, score
