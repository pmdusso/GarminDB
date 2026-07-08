"""BloodB Treinos dashboard DTO built from GarminDB SQLite files.

This is a presentation-facing DTO, not a new persistence layer. It deliberately
reads only allowlisted columns and never exposes activity names, descriptions or
GPS coordinates.
"""

import datetime as _dt
import json
import sqlite3
import statistics
from pathlib import Path


GROUPS = ("cardiovascular", "metabolismo", "carga-performance", "recuperacao-sono")
SERIES_DAYS = 180
BASELINE_DAYS = 90
ACUTE_DAYS = 7
CHRONIC_DAYS = 42
ACWR_DAYS = 28
FTP_ZONES = (
    (1, 0.00, 0.55), (2, 0.56, 0.75), (3, 0.76, 0.90),
    (4, 0.91, 1.05), (5, 1.06, 1.20), (6, 1.21, 1.50), (7, 1.51, None),
)


def build_dashboard(db_dir, config_path=None, period_start=None, period_end=None):
    """Return the Treinos DTO v2 consumed by BloodB's `treinos.js`."""
    end = _parse_date(period_end) if period_end else _dt.date.today()
    start = _parse_date(period_start) if period_start else end - _dt.timedelta(days=SERIES_DAYS)
    cfg = _load_config(config_path)
    builders = {
        "cardiovascular": _build_cardiovascular,
        "metabolismo": _build_metabolismo,
        "carga-performance": _build_carga_performance,
        "recuperacao-sono": _build_recuperacao_sono,
    }
    return {gid: builders[gid](Path(db_dir), cfg, start, end) for gid in GROUPS}


def _parse_date(value):
    return value if isinstance(value, _dt.date) else _dt.date.fromisoformat(str(value)[:10])


def _load_config(config_path):
    if not config_path:
        return {}
    try:
        return json.loads(Path(config_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _query(db_dir, db_name, sql, params=()):
    path = db_dir / db_name
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


def _empty(start, end):
    return {
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "hero": [],
        "main_chart": None,
        "charts": [],
        "insights": [],
    }


def _hero(label, value, unit="", status="neutral", context="", key=None):
    out = {"label": label, "value": value, "unit": unit, "status": status, "context": context}
    if key:
        out["key"] = key
    return out


def _chart(kind, title, x, series, band=None, target=None, default_window=None):
    out = {"kind": kind, "title": title, "x": [_day(v) for v in x], "series": series}
    if band is not None:
        out["band"] = band
    if target is not None:
        out["target"] = target
    if default_window is not None:
        out["default_window"] = default_window
    return out


def _day(value):
    return str(value)[:10]


def _first(rows, col):
    return rows[0][col] if rows else None


def _time_to_hours(value):
    if not value or not isinstance(value, str):
        return None
    try:
        h, m, s = (list(map(float, value.split(":"))) + [0.0, 0.0, 0.0])[:3]
    except ValueError:
        return None
    return h + m / 60 + s / 3600


def _baseline(values, n=BASELINE_DAYS):
    vals = [v for v in values[-n:] if v is not None]
    if len(vals) < 2:
        return None, None
    return statistics.fmean(vals), statistics.pstdev(vals)


def _moving_avg(values, window):
    out = []
    for i, _value in enumerate(values):
        vals = [v for v in values[max(0, i - window + 1):i + 1] if v is not None]
        out.append(round(statistics.fmean(vals), 2) if vals else None)
    return out


def _ewma(values, n):
    out, current = [], None
    for value in values:
        current = value if current is None else current + (value - current) / n
        out.append(current)
    return out


def _weekly_sum(rows, day_key, value_key):
    buckets = {}
    for row in rows:
        value = row[value_key]
        if value is None:
            continue
        day = _dt.date.fromisoformat(_day(row[day_key]))
        monday = (day - _dt.timedelta(days=day.weekday())).isoformat()
        buckets[monday] = buckets.get(monday, 0.0) + float(value)
    x = sorted(buckets)
    return x, [buckets[k] for k in x]


def _ftp_at(cfg, day):
    ftp = None
    for row in sorted(cfg.get("ftp_history", []), key=lambda r: r.get("date", "")):
        if row.get("date", "") <= day.isoformat():
            ftp = row.get("ftp")
    return ftp


def _age(cfg, end):
    try:
        birth = _dt.date.fromisoformat(cfg["birth_date"])
    except (KeyError, ValueError):
        return None
    return end.year - birth.year - ((end.month, end.day) < (birth.month, birth.day))


def _insight(severity, title, body):
    return {"severity": severity, "title": title, "body": body}


def _build_cardiovascular(db_dir, cfg, start, end):
    rhr = _query(db_dir, "garmin_summary.db",
                 "SELECT day, rhr_avg FROM days_summary WHERE day BETWEEN ? AND ? AND rhr_avg IS NOT NULL ORDER BY day",
                 (start.isoformat(), end.isoformat()))
    if not rhr:
        return _empty(start, end)
    rhr_now = _query(db_dir, "garmin.db",
                     "SELECT resting_heart_rate FROM resting_hr WHERE day <= ? AND resting_heart_rate IS NOT NULL ORDER BY day DESC LIMIT 1",
                     (end.isoformat(),))
    spo2 = _query(db_dir, "garmin.db",
                  "SELECT day, spo2_avg, spo2_min FROM daily_summary WHERE day BETWEEN ? AND ? AND spo2_avg IS NOT NULL AND spo2_avg > 0 ORDER BY day",
                  (start.isoformat(), end.isoformat()))
    rr = _query(db_dir, "garmin.db",
                "SELECT day, rr_waking_avg FROM daily_summary WHERE day BETWEEN ? AND ? AND rr_waking_avg IS NOT NULL ORDER BY day",
                (start.isoformat(), end.isoformat()))
    maxhr = _query(db_dir, "garmin_activities.db",
                   "SELECT sport, MAX(max_hr) AS max_hr FROM activities WHERE max_hr IS NOT NULL GROUP BY sport ORDER BY max_hr DESC")

    x = [row["day"] for row in rhr]
    values = [row["rhr_avg"] for row in rhr]
    mean, std = _baseline(values)
    current = _first(rhr_now, "resting_heart_rate")
    status = "warning" if current is not None and mean is not None and current >= mean + 3 else "good"
    media7 = statistics.fmean([v for v in values[-7:] if v is not None]) if values[-7:] else None
    hero = [
        _hero("FC repouso", current, "bpm", status, f"baseline 90d: {mean:.0f}" if mean else "", "resting-heart-rate"),
        _hero("SpO2 última noite", spo2[-1]["spo2_avg"] if spo2 else None, "%"),
        _hero("Respiração ao acordar", rr[-1]["rr_waking_avg"] if rr else None, "rpm"),
    ]
    charts = []
    if spo2:
        charts.append(_chart("lines", "SpO2 (média e mínima da noite)", [r["day"] for r in spo2],
                             [{"label": "Média", "values": [r["spo2_avg"] for r in spo2]},
                              {"label": "Mínima", "values": [r["spo2_min"] for r in spo2]}]))
    if rr:
        charts.append(_chart("lines", "Respiração ao acordar", [r["day"] for r in rr],
                             [{"label": "rpm", "values": [r["rr_waking_avg"] for r in rr]}]))
    insights = []
    if media7 is not None and mean is not None and media7 - mean >= 3:
        insights.append(_insight("warning", f"FC de repouso elevada: média 7d {media7:.0f} bpm",
                                 f"{media7 - mean:.0f} bpm acima da baseline 90d ({mean:.0f})."))
    age = _age(cfg, end)
    for row in maxhr[:3]:
        body = "Teto observado em atividades — referência para zonas de FC."
        if age:
            body += f" Teórica pela idade: {220 - age} bpm."
        insights.append(_insight("info", f"FC máx {_sport_pt(row['sport'])}: {int(row['max_hr'])} bpm", body))
    return {
        "period_start": start.isoformat(), "period_end": end.isoformat(), "hero": hero,
        "main_chart": _chart("line-banded", "FC de repouso vs baseline", x,
                             [{"label": "RHR (média diária)", "values": values}],
                             band={"low": round(mean - std, 1), "high": round(mean + std, 1)} if mean is not None and std is not None else None),
        "charts": charts, "insights": insights,
    }


def _build_metabolismo(db_dir, cfg, start, end):
    weight = _query(db_dir, "garmin.db",
                    "SELECT day, weight FROM weight WHERE day BETWEEN ? AND ? AND weight IS NOT NULL ORDER BY day",
                    (start.isoformat(), end.isoformat()))
    if not weight:
        return _empty(start, end)
    cal = _query(db_dir, "garmin.db",
                 "SELECT day, calories_active, calories_bmr FROM daily_summary WHERE day BETWEEN ? AND ? AND calories_total IS NOT NULL ORDER BY day",
                 (start.isoformat(), end.isoformat()))
    steps = _query(db_dir, "garmin.db",
                   "SELECT day, steps FROM daily_summary WHERE day BETWEEN ? AND ? AND steps IS NOT NULL ORDER BY day",
                   (start.isoformat(), end.isoformat()))
    x = [row["day"] for row in weight]
    values = [row["weight"] for row in weight]
    current = values[-1] if values else None
    target = cfg.get("weight_target") or []
    status = "good" if current is not None and len(target) == 2 and target[0] <= current <= target[1] else "warning" if len(target) == 2 else "neutral"
    steps30 = statistics.fmean([r["steps"] for r in steps[-30:]]) if steps else None
    hero = [
        _hero("Peso", current, "kg", status, f"alvo {target[0]}–{target[1]} kg" if len(target) == 2 else "", "weight"),
        _hero("Calorias (ontem)", (cal[-1]["calories_active"] or 0) + (cal[-1]["calories_bmr"] or 0) if cal else None, "kcal"),
        _hero("Passos (ontem)", steps[-1]["steps"] if steps else None, "", "neutral", f"média 30d: {steps30:.0f}" if steps30 else ""),
    ]
    charts = []
    if cal:
        charts.append(_chart("stacked-bars", "Calorias por dia", [r["day"] for r in cal],
                             [{"label": "BMR", "values": [r["calories_bmr"] for r in cal]},
                              {"label": "Ativas", "values": [r["calories_active"] for r in cal]}],
                             default_window=30))
    if steps:
        xw, vw = _weekly_sum([dict(r) for r in steps], "day", "steps")
        charts.append(_chart("bars", "Passos por semana", xw, [{"label": "Passos", "values": vw, "style": "bars"}]))
    return {
        "period_start": start.isoformat(), "period_end": end.isoformat(), "hero": hero,
        "main_chart": _chart("line-banded", "Peso e média móvel 7d", x,
                             [{"label": "Peso", "values": values}, {"label": "Média móvel 7d", "values": _moving_avg(values, 7)}],
                             band={"low": target[0], "high": target[1]} if len(target) == 2 else None),
        "charts": charts, "insights": [],
    }


def _dense_daily_load(db_dir, start, end):
    rows = _query(db_dir, "garmin_activities.db",
                  "SELECT substr(start_time, 1, 10) AS day, SUM(training_load) AS load FROM activities WHERE substr(start_time, 1, 10) BETWEEN ? AND ? GROUP BY day",
                  (start.isoformat(), end.isoformat()))
    by_day = {r["day"]: (r["load"] or 0.0) for r in rows}
    out, day = [], start
    while day <= end:
        out.append(float(by_day.get(day.isoformat(), 0.0)))
        day += _dt.timedelta(days=1)
    return out


def _build_carga_performance(db_dir, cfg, start, end):
    acts = _query(db_dir, "garmin_activities.db",
                  "SELECT substr(start_time, 1, 10) AS day, sport, distance, "
                  "moving_time, training_load, training_effect, "
                  "anaerobic_training_effect FROM activities "
                  "WHERE substr(start_time, 1, 10) BETWEEN ? AND ?",
                  (start.isoformat(), end.isoformat()))
    if not acts:
        return _empty(start, end)
    warm_start = start - _dt.timedelta(days=CHRONIC_DAYS)
    dense = _dense_daily_load(db_dir, warm_start, end)
    acute = _ewma(dense, ACUTE_DAYS)[CHRONIC_DAYS:]
    chronic = _ewma(dense, CHRONIC_DAYS)[CHRONIC_DAYS:]
    x = []
    day = start
    while day <= end:
        x.append(day.isoformat())
        day += _dt.timedelta(days=1)
    recent = dense[-ACWR_DAYS:]
    acwr = round(statistics.fmean(recent[-ACUTE_DAYS:]) / statistics.fmean(recent), 2) if recent and statistics.fmean(recent) > 0 else None
    form = round(chronic[-1] - acute[-1]) if acute and chronic else None
    status = "good" if form is not None and form > 0 else "warning" if form is not None and form < -10 else "neutral"
    last = max(acts, key=lambda r: r["day"])
    ftp = _ftp_at(cfg, end)
    latest_weight = _query(db_dir, "garmin.db",
                           "SELECT weight FROM weight WHERE day <= ? AND weight IS NOT NULL ORDER BY day DESC LIMIT 1",
                           (end.isoformat(),))
    weight = _first(latest_weight, "weight")
    wkg = round(ftp / weight, 2) if ftp and weight else None
    vo2 = _query(db_dir, "garmin_activities.db",
                 "SELECT c.vo2_max FROM cycle_activities c JOIN activities a ON a.activity_id = c.activity_id WHERE c.vo2_max IS NOT NULL ORDER BY a.start_time DESC LIMIT 1")
    act_rows = [{"day": r["day"], "h": _time_to_hours(r["moving_time"]) or 0, "km": r["distance"] or 0} for r in acts]
    xh, hours = _weekly_sum(act_rows, "day", "h")
    _xk, km = _weekly_sum(act_rows, "day", "km")
    scorecard = []
    if ftp and cfg.get("ftp_target"):
        scorecard.append({"label": "FTP", "current": ftp, "target": cfg["ftp_target"], "unit": "W"})
    if wkg and cfg.get("wkg_target"):
        scorecard.append({"label": "W/kg", "current": wkg, "target": cfg["wkg_target"], "unit": ""})
    if _first(vo2, "vo2_max"):
        scorecard.append({"label": "VO2max bike", "current": _first(vo2, "vo2_max"), "target": None, "unit": ""})
    zones = [{"zone": z, "label": f"Z{z}", "min_w": round(ftp * lo), "max_w": round(ftp * hi) if hi else None} for z, lo, hi in FTP_ZONES] if ftp else []
    return {
        "period_start": start.isoformat(), "period_end": end.isoformat(),
        "hero": [
            _hero("Forma", form, "", status, "crônica − aguda · positivo = fresco", "fitness-balance"),
            _hero("ACWR (7d/28d)", acwr, "", "neutral", "faixa informativa 0,8–1,3"),
            _hero("Última atividade", f"{_sport_pt(last['sport'])} {round(last['distance'] or 0, 1)}km", "", "neutral",
                  f"TE {last['training_effect']} / {last['anaerobic_training_effect']}" if last["training_effect"] is not None else ""),
        ],
        "main_chart": _chart("lines", "Carga aguda × crônica (EPOC)", x,
                             [{"label": "Carga aguda (EPOC 7d)", "values": [round(v, 1) for v in acute]},
                              {"label": "Carga crônica (EPOC 42d)", "values": [round(v, 1) for v in chronic]}]),
        "charts": [_chart("bars", "Volume semanal", xh,
                          [{"label": "Horas", "values": [round(v, 1) for v in hours], "style": "bars"},
                           {"label": "km", "values": [round(v, 1) for v in km], "axis": 2}])],
        "insights": [], "zones": zones, "scorecard": scorecard,
    }


def _build_recuperacao_sono(db_dir, cfg, start, end):
    sleep = _query(db_dir, "garmin.db",
                   "SELECT day, total_sleep, deep_sleep, rem_sleep, light_sleep, score, qualifier, start FROM sleep WHERE day BETWEEN ? AND ? ORDER BY day",
                   (start.isoformat(), end.isoformat()))
    if not sleep:
        return _empty(start, end)
    hrv = _query(db_dir, "garmin.db",
                 "SELECT day, weekly_avg, last_night_avg, status, baseline_low, baseline_upper FROM hrv WHERE day BETWEEN ? AND ? ORDER BY day",
                 (start.isoformat(), end.isoformat()))
    stress = _query(db_dir, "garmin.db",
                    "SELECT day, stress_avg, bb_charged, bb_max, bb_min FROM daily_summary WHERE day BETWEEN ? AND ? AND stress_avg IS NOT NULL ORDER BY day",
                    (start.isoformat(), end.isoformat()))
    readiness = _latest_readiness(db_dir, end)
    target = cfg.get("sleep_target_h", 7.5)
    x = [r["day"] for r in sleep]
    deep = [_time_to_hours(r["deep_sleep"]) for r in sleep]
    rem = [_time_to_hours(r["rem_sleep"]) for r in sleep]
    light = [_time_to_hours(r["light_sleep"]) for r in sleep]
    total = [_time_to_hours(r["total_sleep"]) for r in sleep]
    scores = [r["score"] for r in sleep]
    hrv_last = hrv[-1] if hrv else None
    hrv_status = (
        "good"
        if hrv_last and hrv_last["last_night_avg"] and hrv_last["baseline_low"]
        and hrv_last["last_night_avg"] >= hrv_last["baseline_low"]
        else "warning" if hrv_last else "neutral"
    )
    charts = []
    if hrv:
        charts.append(_chart("line-banded", "HRV vs baseline", [r["day"] for r in hrv],
                             [{"label": "HRV noturna", "values": [r["last_night_avg"] for r in hrv]}],
                             band={"low": hrv_last["baseline_low"], "high": hrv_last["baseline_upper"]} if hrv_last and hrv_last["baseline_low"] else None))
    if stress:
        charts.append(_chart("dual-axis", "Stress × Body Battery", [r["day"] for r in stress],
                             [{"label": "Stress médio", "values": [r["stress_avg"] for r in stress]},
                              {"label": "BB carga noturna", "values": [r["bb_charged"] for r in stress], "axis": 2}]))
    insights = []
    last_sleep = next((v for v in reversed(total) if v is not None), None)
    if last_sleep is not None and last_sleep < 5:
        insights.append(_insight("critical", "Sono insuficiente", f"Última noite com {last_sleep:.1f}h de sono total."))
    elif last_sleep is not None and last_sleep < 6:
        insights.append(_insight("warning", "Sono abaixo do ideal", f"Última noite com {last_sleep:.1f}h de sono total."))
    if readiness and readiness.get("feedback_short"):
        insights.append(_insight("info", "Prontidão do dia", _readiness_pt(readiness["feedback_short"])))
    return {
        "period_start": start.isoformat(), "period_end": end.isoformat(),
        "hero": [
            _hero("Prontidão", readiness["score"] if readiness else None, "", "neutral",
                  f"Training Readiness · último em {readiness['day']}" if readiness else "sem dado"),
            _hero("Sleep score", next((s for s in reversed(scores) if s is not None), None), "", "neutral", "", "sleep-score"),
            _hero("HRV (última noite)", hrv_last["last_night_avg"] if hrv_last else None, "ms", hrv_status,
                  f"baseline {hrv_last['baseline_low']:.0f}–{hrv_last['baseline_upper']:.0f}" if hrv_last and hrv_last["baseline_low"] else ""),
        ],
        "main_chart": _chart("stacked-bars", "Sono por estágio", x,
                             [{"label": "Profundo", "values": [round(v, 2) if v else None for v in deep]},
                              {"label": "REM", "values": [round(v, 2) if v else None for v in rem]},
                              {"label": "Leve", "values": [round(v, 2) if v else None for v in light]}],
                             target=target, default_window=30),
        "charts": charts, "insights": insights,
    }


def _latest_readiness(db_dir, end):
    rows = _query(db_dir, "garmin.db",
                  "SELECT day, timestamp, score, level, feedback_short, recovery_time FROM training_readiness WHERE day <= ? ORDER BY day DESC, timestamp DESC LIMIT 1",
                  (end.isoformat(),))
    if not rows:
        return None
    row = rows[0]
    day = _day(row["day"] or row["timestamp"])
    try:
        stale = _dt.date.fromisoformat(day) < end - _dt.timedelta(days=1)
    except ValueError:
        stale = True
    return {
        "day": day, "score": row["score"], "level": row["level"],
        "feedback_short": row["feedback_short"], "recovery_time_hours": row["recovery_time"],
        "is_stale": stale,
    }


def _sport_pt(sport):
    labels = {"running": "corrida", "cycling": "ciclismo", "swimming": "natação", "walking": "caminhada",
              "hiking": "trilha", "fitness_equipment": "academia", "training": "treino"}
    key = str(sport or "").lower()
    return labels.get(key, key.replace("_", " "))


def _readiness_pt(feedback):
    labels = {
        "READY": "Pronto para treinar",
        "TRAINING_READY": "Pronto para treinar",
        "RECOVERY_IN_PROGRESS": "Recuperação em andamento",
        "RECOVERED": "Recuperado",
        "REST_DAY_RECOMMENDED": "Descanso recomendado",
        "LOW_SLEEP": "Sono baixo",
        "HIGHLY_READY": "Prontidão alta",
    }
    key = str(feedback or "").upper()
    return labels.get(key, key.replace("_", " ").capitalize() or "")
