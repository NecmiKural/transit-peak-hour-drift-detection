"""Streaming drift detection on the peak boundaries (CapyMOA, MOA-backed).

We feed the per-day peak-start times (in minutes-of-day) into a change
detector and flag the days where the boundary regime shifts, e.g. the
morning peak moving earlier/later between weekdays and weekends, around
holidays, or on rainy days.

Requires Java 17 at runtime (CapyMOA wraps MOA via JPype).

From Assignment 2: CapyMOA's MOADriftDetector appends every
observation to a Python-side `data` list that the Java algorithm never
reads, which leaks memory on long streams. We don't reset()/long-run here at
scale, but if you do, subclass and skip that append.
"""
from __future__ import annotations

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
import config as C


def make_detector(kind: str = "adwin"):
    """Return a CapyMOA detector. kind in {'adwin','pagehinkley','cusum'}."""
    from capymoa.drift.detectors import ADWIN, PageHinkley, CUSUM  # lazy import (needs Java 17)

    if kind == "adwin":
        return ADWIN(delta=C.ADWIN_DELTA)
    if kind == "pagehinkley":
        return PageHinkley()
    if kind == "cusum":
        return CUSUM()
    raise ValueError(f"unknown detector: {kind}")


class _PageHinkleyDev:
    """DEV-ONLY pure-Python Page-Hinkley, used *only* when CapyMOA can't be
    imported (e.g. no Java 17) so the pipeline can be demoed offline.

    NOT for the submission: the graded results must use the CapyMOA detector
    via make_detector(). Any output produced with this backend is stamped
    'DEV' by the analysis script.
    """

    def __init__(self, delta=0.005, lambda_=8.0, alpha=0.999):
        self.delta, self.lambda_, self.alpha = delta, lambda_, alpha
        self.mean = 0.0
        self.n = 0
        self.cum = 0.0
        self.min_cum = 0.0
        self._change = False

    def add_element(self, x: float):
        self.n += 1
        self.mean += (x - self.mean) / self.n
        self.cum = self.alpha * self.cum + (x - self.mean - self.delta)
        self.min_cum = min(self.min_cum, self.cum)
        self._change = (self.cum - self.min_cum) > self.lambda_

    def detected_change(self) -> bool:
        return self._change

    def reset(self):
        self.__init__(self.delta, self.lambda_, self.alpha)


def get_detector(kind: str = "adwin", allow_dev_fallback: bool = False):
    """Return (detector, backend_name). Prefers CapyMOA; falls back to the
    DEV Page-Hinkley only if explicitly allowed and CapyMOA is unavailable."""
    try:
        return make_detector(kind), "capymoa"
    except Exception as e:  # ImportError / no JVM
        if allow_dev_fallback:
            import warnings
            warnings.warn(f"CapyMOA unavailable ({e}); using DEV Page-Hinkley "
                          f"fallback, NOT for submission.")
            return _PageHinkleyDev(delta=C.PAGE_HINKLEY_DELTA), "DEV-fallback"
        raise


def detect_boundary_drift(daily_starts, kind: str = "adwin", allow_dev_fallback: bool = False):
    """daily_starts: list of (date, start_minute).
    Returns (list of (date, start_minute) where drift fired, backend_name)."""
    det, backend = get_detector(kind, allow_dev_fallback)
    drifts = []
    for date, minute in daily_starts:
        det.add_element(float(minute))
        if det.detected_change():
            drifts.append((date, minute))
    return drifts, backend


if __name__ == "__main__":
    # Example: a boundary that jumps from ~06:50 (410) to ~06:10 (370).
    series = [("d%02d" % i, 410 if i < 20 else 370) for i in range(40)]
    drifts, backend = detect_boundary_drift(series, "adwin", allow_dev_fallback=True)
    print(f"backend={backend}  drift days:", drifts)
