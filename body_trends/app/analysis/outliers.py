"""Hampel filter: flag points far from the rolling median, scaled by the MAD."""
import numpy as np

MAD_TO_SIGMA = 1.4826


def hampel_mask(values, window: int = 7, sigmas: float = 3.5) -> np.ndarray:
    """True where a value is an outlier. `window` is the full width in points."""
    v = np.asarray(values, dtype=float)
    n, half = len(v), max(1, window // 2)
    mask = np.zeros(n, dtype=bool)
    for i in range(n):
        seg = v[max(0, i - half): i + half + 1]
        if len(seg) < 4:
            continue
        med = np.median(seg)
        # Floor keeps a perfectly flat stretch from flagging every tiny wobble.
        scale = max(MAD_TO_SIGMA * np.median(np.abs(seg - med)), 0.005 * abs(med), 1e-9)
        mask[i] = abs(v[i] - med) > sigmas * scale
    return mask
