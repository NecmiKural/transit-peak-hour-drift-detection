"""Brazil / Bahia public holidays inside the data window (Mar-May 2024).

Used to test whether peak boundaries shift on holidays / bridge days.
Notable holidays in the window: Good Friday (2024-03-29), Tiradentes
(2024-04-21), Labour Day (2024-05-01), Corpus Christi (2024-05-30).
Salvador municipal: 2 de Julho is outside the window.
"""
from __future__ import annotations

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
import config as C


def holiday_dates(year: int = 2024) -> set[str]:
    """Set of 'YYYY-MM-DD' holiday strings for Bahia/Brazil in the window."""
    import holidays

    bahia = holidays.Brazil(years=year, subdiv="BA")
    out = {
        d.isoformat() for d in bahia
        if C.DATE_START <= d.isoformat() <= C.DATE_END
    }
    return out


def is_holiday(ts, cache: set[str] | None = None) -> int:
    cache = cache if cache is not None else holiday_dates(ts.year)
    return int(str(ts.date()) in cache)


if __name__ == "__main__":
    print("holidays in window:", sorted(holiday_dates(2024)))
