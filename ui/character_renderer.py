"""Reusable Matplotlib marker artists; no network or image decoding on the GUI thread."""
from __future__ import annotations

import numpy as np
from matplotlib.offsetbox import DrawingArea, OffsetImage
from matplotlib.patches import Ellipse, PathPatch
from matplotlib.path import Path
from matplotlib.text import Text


class CharacterRenderer:
    def __init__(self) -> None:
        self._vectors: dict[tuple[int, str, str], DrawingArea] = {}
        self._photos: dict[int, OffsetImage] = {}

    def set_headshot(self, mlbam_id: int, rgba: np.ndarray) -> None:
        self._photos[mlbam_id] = OffsetImage(rgba, zoom=1, dpi_cor=False)

    def marker(self, mlbam_id: int, name: str, color: str,
               mode: str = 'vector') -> DrawingArea | OffsetImage:
        """Reuse artwork across scrubbing; missing headshots immediately use helmets."""
        if mode == 'headshot' and mlbam_id in self._photos:
            return self._photos[mlbam_id]
        initial = name.strip()[:1].upper() or '?'
        key = (mlbam_id, initial, color)
        if key not in self._vectors:
            area = DrawingArea(38, 38)
            outline = '#172033'
            dome = Path([(4, 15), (2, 34), (30, 38), (32, 16), (4, 15)],
                        [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4, Path.CLOSEPOLY])
            area.add_artist(PathPatch(dome, facecolor=color, edgecolor=outline, lw=1.1))
            area.add_artist(Ellipse((17, 29), 18, 7, angle=15, color='white', alpha=.22))
            brim = Path([(3, 17), (31, 19), (38, 13), (9, 12), (3, 17)],
                        [Path.MOVETO, Path.LINETO, Path.LINETO, Path.LINETO, Path.CLOSEPOLY])
            area.add_artist(PathPatch(brim, facecolor=color, edgecolor=outline, lw=1.1))
            area.add_artist(Ellipse((10, 12), 10, 17, facecolor=color, edgecolor=outline, lw=1.1))
            area.add_artist(Ellipse((10, 12), 3, 5, facecolor=outline))
            area.add_artist(Text(22, 24, initial, ha='center', va='center',
                                 color='white', fontsize=10, weight='bold'))
            self._vectors[key] = area
        return self._vectors[key]
