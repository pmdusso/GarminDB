"""Treinos reports built from GarminDB rollups."""

import datetime as _dt
import sqlite3
from pathlib import Path

from .treinos_rollups import daily_hrv_series, daily_training_load_rows


def build_carga_recuperacao_report(db_dir, period_start=None, period_end=None):
    end = _parse_date(period_end) if period_end else _dt.date.today()
    start = _parse_date(period_start) if period_start else end - _dt.timedelta(days=90)
    db_dir = Path(db_dir)
    load_rows = daily_training_load_rows(db_dir, start, end)
    sleep = _sleep_rows(db_dir, start, end)
    hrv = {r["day"]: r for r in daily_hrv_series(db_dir, start, end)}
    readiness = _readiness_rows(db_dir, start, end)
    weeks = _weekly(load_rows, sleep, hrv, readiness)
    insights = _insights(weeks)
    return {
        "kind": "carga-recuperacao",
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "weeks": weeks,
        "insights": insights,
    }


def render_carga_recuperacao_markdown(report):
    lines = [
        "# Carga x Recuperação",
        "",
        f"Período: {report['period_start']} -> {report['period_end']}",
        "",
        "| Semana | Carga | Sono médio | HRV média | Readiness | Risco |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for week in report["weeks"]:
        lines.append(
            f"| {week['week_start']} | {_num(week['load'], 0)} | "
            f"{_num(week['sleep_avg_h'], 1)}h | {_num(week['hrv_avg_ms'], 0)} ms | "
            f"{_num(week['readiness_avg'], 0)} | {week['risk']} |"
        )
    if report["insights"]:
        lines += ["", "## Leituras", ""]
        lines += [f"- **{i['title']}**: {i['body']}" for i in report["insights"]]
    return "\n".join(lines) + "\n"


def _weekly(load_rows, sleep, hrv, readiness):
    buckets = {}
    for row in load_rows:
        week = _week(row["day"])
        b = buckets.setdefault(week, _bucket(week))
        b["load"] += float(row["load"] or 0)
        b["duration_hours"] += float(row["duration_hours"] or 0)
        b["activities_count"] += int(row["activities_count"] or 0)
    for day, row in sleep.items():
        b = buckets.setdefault(_week(day), _bucket(_week(day)))
        if row["hours"] is not None:
            b["_sleep"].append(row["hours"])
    for day, row in hrv.items():
        b = buckets.setdefault(_week(day), _bucket(_week(day)))
        if row["last_night_avg"] is not None:
            b["_hrv"].append(float(row["last_night_avg"]))
    for day, score in readiness.items():
        b = buckets.setdefault(_week(day), _bucket(_week(day)))
        if score is not None:
            b["_readiness"].append(float(score))
    out = []
    for b in buckets.values():
        sleep_avg = _avg(b["_sleep"])
        hrv_avg = _avg(b["_hrv"])
        readiness_avg = _avg(b["_readiness"])
        risk = "warning" if (sleep_avg is not None and sleep_avg < 6.5) or (readiness_avg is not None and readiness_avg < 50) else "ok"
        out.append({
            "week_start": b["week_start"],
            "load": round(b["load"], 2),
            "duration_hours": round(b["duration_hours"], 2),
            "activities_count": b["activities_count"],
            "sleep_avg_h": sleep_avg,
            "hrv_avg_ms": hrv_avg,
            "readiness_avg": readiness_avg,
            "risk": risk,
        })
    return sorted(out, key=lambda r: r["week_start"])


def _bucket(week):
    return {"week_start": week, "load": 0.0, "duration_hours": 0.0, "activities_count": 0, "_sleep": [], "_hrv": [], "_readiness": []}


def _insights(weeks):
    if not weeks:
        return [{"severity": "info", "title": "Sem carga no período", "body": "Nenhum treino com carga encontrado."}]
    flagged = [w for w in weeks if w["risk"] == "warning"]
    if flagged:
        last = flagged[-1]
        return [{"severity": "warning", "title": "Semana com recuperação pressionada",
                 "body": f"{last['week_start']}: sono/readiness abaixo do ideal com carga {_num(last['load'], 0)}."}]
    return [{"severity": "good", "title": "Carga compatível com recuperação",
             "body": "Sem semanas com sono médio baixo ou readiness abaixo de 50."}]


def _sleep_rows(db_dir, start, end):
    rows = _query(
        db_dir, "garmin.db",
        "SELECT day, total_sleep, score FROM sleep WHERE day BETWEEN ? AND ?",
        (start.isoformat(), end.isoformat()),
    )
    return {_day(r["day"]): {"hours": _time_to_hours(r["total_sleep"]), "score": r["score"]} for r in rows}


def _readiness_rows(db_dir, start, end):
    rows = _query(
        db_dir, "garmin.db",
        "SELECT day, score FROM training_readiness WHERE day BETWEEN ? AND ?",
        (start.isoformat(), end.isoformat()),
    )
    return {_day(r["day"]): r["score"] for r in rows}


def _query(db_dir, db_name, sql, params=()):
    path = Path(db_dir) / db_name
    if not path.exists():
        return []
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            return con.execute(sql, params).fetchall()
        finally:
            con.close()
    except (sqlite3.Error, OSError):
        return []


def _parse_date(value):
    return value if isinstance(value, _dt.date) else _dt.date.fromisoformat(str(value)[:10])


def _week(day):
    d = _parse_date(day)
    return (d - _dt.timedelta(days=d.weekday())).isoformat()


def _time_to_hours(value):
    if not value:
        return None
    try:
        h, m, s = (list(map(float, str(value).split(":"))) + [0.0, 0.0, 0.0])[:3]
    except ValueError:
        return None
    return h + m / 60 + s / 3600


def _avg(values):
    return round(sum(values) / len(values), 2) if values else None


def _num(value, decimals):
    if value is None:
        return "—"
    return f"{value:.{decimals}f}"


def _day(value):
    return str(value)[:10]
