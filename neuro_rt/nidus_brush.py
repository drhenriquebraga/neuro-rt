"""A physical brush disk swept along an MPR stroke; no inter-slice interpolation."""
import math

import numpy as np


def stroke_mask_mm(shape, spacing_rc, points, radius_mm):
    if (len(shape) != 2 or min(shape) < 1 or math.prod(shape) > 16_000_000 or
            not isinstance(points, list) or not 1 <= len(points) <= 256):
        raise ValueError('Traço ou plano do pincel inválido.')
    try:
        radius = float(radius_mm)
        row_mm, col_mm = (float(v) for v in spacing_rc)
        if (isinstance(radius_mm, bool) or not math.isfinite(radius) or not .1 <= radius <= 50 or
                not all(math.isfinite(v) and v > 0 for v in (row_mm, col_mm))):
            raise ValueError()
        values = np.asarray(points, dtype=np.float64)
        if values.shape != (len(points), 2) or not np.isfinite(values).all() or (values < 0).any() or (values > 1).any():
            raise ValueError()
    except (ValueError, TypeError, OverflowError):
        raise ValueError('Raio ou coordenadas do pincel inválidos.') from None
    height, width = shape
    # Normalized view coordinates denote pixel edges; centers are (i + .5).
    path = values * np.array([width * col_mm, height * row_mm])
    segments = list(zip(path[:-1], path[1:])) if len(path) > 1 else [(path[0], path[0])]
    mask = np.zeros(shape, dtype=bool)
    evaluated = 0
    for start, end in segments:
        x0 = max(0, math.floor((min(start[0], end[0]) - radius) / col_mm - .5))
        x1 = min(width, math.ceil((max(start[0], end[0]) + radius) / col_mm + .5))
        y0 = max(0, math.floor((min(start[1], end[1]) - radius) / row_mm - .5))
        y1 = min(height, math.ceil((max(start[1], end[1]) + radius) / row_mm + .5))
        evaluated += (x1 - x0) * (y1 - y0)
        if evaluated > 64_000_000:
            raise ValueError('Divida este traço em movimentos menores.')
        x = (np.arange(x0, x1) + .5) * col_mm
        y = ((np.arange(y0, y1) + .5) * row_mm)[:, None]
        dx, dy = end - start
        norm = dx * dx + dy * dy
        t = np.clip(((x - start[0]) * dx + (y - start[1]) * dy) / norm, 0, 1) if norm > 1e-20 else 0.
        distance2 = (x - start[0] - t * dx) ** 2 + (y - start[1] - t * dy) ** 2
        mask[y0:y1, x0:x1] |= distance2 <= radius * radius + 1e-10
    return mask
