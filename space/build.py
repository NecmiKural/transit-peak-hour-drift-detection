"""Build the static Hugging Face Space page from the CSVs in outputs/.

    python3 space/build.py

Writes space/index.html: plain HTML with inline SVG charts, no scripts. Every number on the
page comes from a file in outputs/ or, for the headline table, from README.md verbatim.
"""

import csv
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "space" / "index.html"
REPO = "https://github.com/NecmiKural/transit-peak-hour-drift-detection"

# The five (stop, period) series in the README headline table, in its order.
HEADLINE = [
    ("Lapa Station", "AM", "06:00"),
    ("Salvador Bus Station", "PM", "17:00"),
    ("Lacerda Elevator", "PM", "17:00"),
    ("Shopping mall", "PM", "17:00"),
    ("Castro Alves Theater", "PM", "17:00"),
]


def rows(name: str) -> list[dict]:
    with open(ROOT / "outputs" / name, newline="") as f:
        return list(csv.DictReader(f))


def minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def clock(mins: float) -> str:
    return f"{int(mins) // 60:02d}:{int(mins) % 60:02d}"


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def headline_table() -> str:
    """The README's headline table, copied verbatim (bold markers dropped)."""
    text = (ROOT / "README.md").read_text()
    block = text.split("| Stop | Period |", 1)[1].split("\n\n", 1)[0]
    lines = ["| Stop | Period |" + block.split("\n", 1)[0]] + block.split("\n")[1:]
    cells = [[c.strip().strip("*") for c in ln.strip("|").split("|")] for ln in lines if ln.strip()]
    head, body = cells[0], [r for r in cells[2:]]
    th = "".join(f'<th scope="col">{esc(c)}</th>' for c in head)
    trs = "".join(
        "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in body
    )
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


def strip(label: str, period: str, official: str, points: list[dict]) -> str:
    """One stop: each detected daily start as a dot, weekdays and weekends in two lanes."""
    w, h, left, right = 640, 96, 112, 16
    starts = [int(p["start_min"]) for p in points]
    lo = (min(starts + [minutes(official)]) // 60) * 60
    hi = -(-max(starts + [minutes(official)]) // 60) * 60
    span = max(hi - lo, 60)

    def x(m: float) -> float:
        return left + (m - lo) / span * (w - left - right)

    lanes = {"weekday": 34, "weekend": 66}
    # Starts come in 5-minute steps, so days often share a time: one mark per time, sized by
    # how many days share it.
    counts: dict[tuple[str, int], int] = {}
    for p in points:
        lane = "weekday" if p["weekend"] == "0" and p["holiday"] == "0" else "weekend"
        key = (lane, int(p["start_min"]))
        counts[key] = counts.get(key, 0) + 1
    marks = []
    for (lane, start), n in sorted(counts.items()):
        cx, cy, r = x(start), lanes[lane], 2.5 + 1.6 * n**0.5
        if lane == "weekday":
            marks.append(f'<circle class="weekday" cx="{cx:.1f}" cy="{cy}" r="{r:.1f}"/>')
        else:
            marks.append(
                f'<rect class="weekend" x="{cx - r:.1f}" y="{cy - r:.1f}" width="{2 * r:.1f}" height="{2 * r:.1f}"/>'
            )
    ticks = []
    for m in range(lo, hi + 1, 60):
        ticks.append(
            f'<line class="grid" x1="{x(m):.1f}" x2="{x(m):.1f}" y1="18" y2="80"/>'
            f'<text class="tick" x="{x(m):.1f}" y="94" text-anchor="middle">{clock(m)}</text>'
        )
    ox = x(minutes(official))
    slug = re.sub(r"\W+", "-", f"{label}-{period}").lower()
    title = f"{label}, {period}: detected daily peak start, {len(points)} days"
    desc = (
        f"Each mark is one day's detected start of the {period} peak at {label}. Circles are "
        f"weekdays, squares weekends and holidays; a larger mark is several days at the same "
        f"time. The dashed line is the official {official}."
    )
    return (
        f'<figure><figcaption>{esc(label)} <span class="quiet">{period}, {len(points)} days</span></figcaption>'
        f'<div class="chart" tabindex="0" role="region" aria-label="{esc(title)}">'
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="t-{slug}">'
        f'<title id="t-{slug}">{esc(title)}</title><desc>{esc(desc)}</desc>'
        f'<text class="lane" x="0" y="38">weekday</text><text class="lane" x="0" y="70">weekend</text>'
        f'{"".join(ticks)}'
        f'<line class="official" x1="{ox:.1f}" x2="{ox:.1f}" y1="14" y2="82"/>'
        f'<text class="official-label" x="{ox + 4:.1f}" y="12">official {official}</text>'
        f'{"".join(marks)}</svg></div></figure>'
    )


def peak_strips() -> str:
    points = rows("boundary_points_real.csv")
    return "".join(
        strip(label, period, official, [p for p in points if p["label"] == label and p["period"] == period])
        for label, period, official in HEADLINE
    )


def drift_chart() -> str:
    data = rows("role_d_concept_drift.csv")
    data = [d for d in data if not d["stop"].startswith("#")]
    w, bar_h, gap, left = 640, 18, 10, 172
    top = max(int(d["perinstance_adwin_detections"]) for d in data)
    h = len(data) * (bar_h + gap) + 30
    out = []
    for i, d in enumerate(data):
        y = 20 + i * (bar_h + gap)
        n = int(d["perinstance_adwin_detections"])
        bw = n / top * (w - left - 150)
        out.append(
            f'<text class="tick" x="{left - 8}" y="{y + 13}" text-anchor="end">{esc(d["label"])}</text>'
            f'<rect class="bar" x="{left}" y="{y}" width="{bw:.1f}" height="{bar_h}"/>'
            f'<text class="value" x="{left + bw + 6:.1f}" y="{y + 13}">{n} alarms, '
            f'{d["daily_rmse_adwin_drift_days"]} drift days</text>'
        )
    desc = (
        "For each stop, the number of ADWIN alarms on the model's per-instance error, next to "
        "the drift days ADWIN finds on the per-day RMSE series, which is zero for every stop."
    )
    return (
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="t-drift">'
        f'<title id="t-drift">ADWIN alarms per stop, per instance and per day</title><desc>{esc(desc)}</desc>'
        f'{"".join(out)}</svg>'
    )


def schedule_chart() -> str:
    data = [d for d in rows("schedule_alignment.csv") if d["gap_min"] and d["day_type"] == "weekday"]
    w, bar_h, gap, left = 640, 16, 8, 210
    zero = left + 40
    top = max(abs(float(d["gap_min"])) for d in data)
    scale = (w - zero - 250) / top  # room for the longest label after the longest bar
    h = len(data) * (bar_h + gap) + 30
    out = [f'<line class="grid" x1="{zero}" x2="{zero}" y1="10" y2="{h - 10}"/>']
    for i, d in enumerate(data):
        y = 14 + i * (bar_h + gap)
        g = float(d["gap_min"])
        x0, bw = (zero, g * scale) if g >= 0 else (zero + g * scale, -g * scale)
        cls = "bar" if g >= 0 else "bar early"
        out.append(
            f'<text class="tick" x="{left - 8}" y="{y + 12}" text-anchor="end">{esc(d["label"])}, {d["period"]}</text>'
            f'<rect class="{cls}" x="{x0:.1f}" y="{y}" width="{bw:.1f}" height="{bar_h}"/>'
            f'<text class="value" x="{(zero + g * scale + 6) if g >= 0 else (zero + 6):.1f}" y="{y + 12}">'
            f'{"+" if g >= 0 else ""}{g:.0f} min (timetable {d["scheduled_peak"]}, demand {d["demand_peak"]})</text>'
        )
    desc = (
        "Weekday gap between the timetable's busiest arrival time and the detected demand peak, "
        "per stop and period. Positive bars mean demand peaks later than the timetable."
    )
    return (
        f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="t-sched">'
        f'<title id="t-sched">Timetable peak against demand peak, weekdays</title><desc>{esc(desc)}</desc>'
        f'{"".join(out)}</svg>'
    )


def page() -> str:
    template = (ROOT / "space" / "template.html").read_text()
    parts = {
        "headline": headline_table(),
        "strips": peak_strips(),
        "drift": drift_chart(),
        "schedule": schedule_chart(),
        "repo": REPO,
    }
    out = template
    for key, value in parts.items():
        out = out.replace("{{" + key + "}}", value)
    assert not re.search(r"\{\{\w+\}\}", out), "unfilled placeholder"
    return out


if __name__ == "__main__":
    OUT.write_text(page())
    print(f"wrote {OUT.relative_to(ROOT)}")
