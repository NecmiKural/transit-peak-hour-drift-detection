"""Online adaptive-threshold peak-boundary detector.

Everything here is incremental (one interval at a time) so it stays within
the streaming constraint, no full-day batch is ever held in memory.

Idea:
  * keep an EWMA running mean + variance of the *off-peak* boarding rate;
  * an interval is "high" when value > mean + K * std;
  * MIN_SUSTAIN consecutive high intervals confirm a peak; the boundary is
    backdated to where the run started (the real peak start);
  * a drop back below threshold closes the peak (the peak end).
The baseline is updated only while NOT in a peak, so peak mass doesn't
inflate the threshold.

Output: a list of boundary events (date, period AM/PM, start, end) that the
drift layer (src/drift.py) then watches for shift over time.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
import config as C


@dataclass
class PeakEvent:
    date: str
    period: str          # "AM" or "PM"
    start: object        # timestamp of peak start
    end: object | None   # timestamp of peak end (None if still open)
    start_minute: int    # minute-of-day of start (for drift tracking)


@dataclass
class OnlinePeakDetector:
    alpha: float = C.EWMA_ALPHA
    k: float = C.THRESH_K
    min_abs: float = C.MIN_ABS_LIFT
    min_sustain: int = C.MIN_SUSTAIN
    warmup: int = 200

    # internal incremental state
    _mean: float = 0.0
    _var: float = 1.0
    _n: int = 0
    _run: int = 0
    _in_peak: bool = False
    _cur: PeakEvent | None = None
    _pending: list = field(default_factory=list)  # timestamps of the current high run
    events: list = field(default_factory=list)

    def _threshold(self) -> float:
        return self._mean + self.k * math.sqrt(max(self._var, 1e-9))

    def update(self, ts, value: float):
        """Process one 5-minute interval. Returns a PeakEvent when one closes, else None."""
        self._n += 1
        mod = ts.hour * 60 + ts.minute
        if mod < 12 * 60:
            period, window = "AM", C.AM_WINDOW
        else:
            period, window = "PM", C.PM_WINDOW
        in_window = window[0] <= mod <= window[1]
        closed = None

        if self._n <= self.warmup:
            self._ewma(value)
            return None

        # A peak interval must clear both a relative and an absolute lift, and
        # fall inside the morning/evening search window.
        high = (in_window
                and value > self._threshold()
                and value > self._mean + self.min_abs)

        if high:
            self._run += 1
            self._pending.append(ts)
            if not self._in_peak and self._run >= self.min_sustain:
                start_ts = self._pending[0]
                self._in_peak = True
                self._cur = PeakEvent(
                    date=str(ts.date()), period=period, start=start_ts,
                    end=None, start_minute=start_ts.hour * 60 + start_ts.minute,
                )
        else:
            if self._in_peak and self._cur is not None:
                self._cur.end = ts
                self.events.append(self._cur)
                closed = self._cur
                self._cur = None
                self._in_peak = False
            self._run = 0
            self._pending.clear()
            self._ewma(value)  # update baseline only off-peak

        return closed

    def _ewma(self, x: float):
        diff = x - self._mean
        self._mean += self.alpha * diff
        self._var = (1 - self.alpha) * (self._var + self.alpha * diff * diff)

    def daily_starts(self, period: str = "AM"):
        """(date, start_minute) for each day, the series the drift layer watches."""
        return [(e.date, e.start_minute) for e in self.events if e.period == period]


if __name__ == "__main__":
    # smoke test on a synthetic daily-peak signal
    import datetime as dt
    det = OnlinePeakDetector(warmup=50)
    base = dt.datetime(2024, 3, 1)
    for day in range(5):
        for i in range(288):  # 5-min intervals in a day
            ts = base + dt.timedelta(days=day, minutes=5 * i)
            m = ts.hour * 60 + ts.minute
            val = 5 + (20 if 410 <= m <= 540 else 0)  # ~06:50-09:00 morning peak
            det.update(ts, val)
    print("AM starts:", det.daily_starts("AM"))
