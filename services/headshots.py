"""Bounded headshot download and image preparation, executed only in workers."""
from __future__ import annotations

from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw

from cache.file_cache import HeadshotCache
from services.base_http import async_get_bytes

HEADSHOT_URL = ('https://img.mlbstatic.com/mlb-photos/image/upload/'
                'd_people:generic:headshot:67:current.png/w_60,q_auto:best/'
                'v1/people/{mlbam_id}/headshot/67/current.png')


def circular_thumbnail(data: bytes) -> np.ndarray:
    """Decode a bounded image into a 32px circular RGBA thumbnail."""
    with Image.open(BytesIO(data)) as source:
        if source.width * source.height > 4_000_000:
            raise ValueError('Headshot dimensions too large')
        picture = source.convert('RGBA').resize((32, 32), Image.Resampling.LANCZOS)
    mask = Image.new('L', (32, 32))
    ImageDraw.Draw(mask).ellipse((0, 0, 31, 31), fill=255)
    # Preserve existing transparent pixels as well as the circular mask.
    alpha = np.minimum(np.asarray(picture.getchannel('A')), np.asarray(mask))
    picture.putalpha(Image.fromarray(alpha))
    return np.asarray(picture).copy()


async def load_headshot(mlbam_id: int, cache: HeadshotCache | None = None) -> np.ndarray | None:
    """Return None on any transport/cache/decode failure for seamless vector fallback."""
    try:
        cache = cache or HeadshotCache()
        path = cache.path_for(mlbam_id)
        if path.exists():
            try:
                return circular_thumbnail(path.read_bytes())
            except (OSError, ValueError):
                pass
        data = await async_get_bytes(HEADSHOT_URL.format(mlbam_id=mlbam_id), timeout=10, retries=1)
        thumbnail = circular_thumbnail(data)
        normalized = BytesIO()
        Image.fromarray(thumbnail).save(normalized, format='PNG')
        cache.write(mlbam_id, normalized.getvalue())
        return thumbnail
    except Exception:
        return None
