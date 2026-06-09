"""Render a :class:`LongitudinalReport` to clinician-facing Markdown (pt-BR).

Layout follows sports-medicine anamnesis norms: lead with an executive panel
(current vs personal baseline vs direction of travel), then a *red-flags-first*
block, then one section per metric family with a unicode sparkline, a
months-as-rows table of the real numbers, and a short interpretation. A closing
provenance/limitations section states that the values are Garmin device
estimates (screening, not diagnostic) and that no power data exists.
"""

import logging
from typing import Dict, List, Optional, Tuple

from garmindb.analysis.longitudinal_report import (
    LongitudinalReport, MetricSeries, TrainingLoadMonth, VolumeMonth,
)

logger = logging.getLogger(__name__)

_NO_VALUE = "—"

_SEX_PT = {"male": "masculino", "female": "feminino"}
_SPORT_PT = {
    "cycling": "ciclismo",
    "running": "corrida",
    "fitness_equipment": "musculação",
    "hiking": "trilha",
    "walking": "caminhada",
    "swimming": "natação",
    "training": "treino",
    "paddling": "remo (SUP)",
    "kayaking": "caiaque",
    "snowmobiling": "snowmobile",
    "generic": "outro",
    "unknown": "outro",
}


def _num(value: Optional[float], decimals: int = 1) -> str:
    if value is None:
        return _NO_VALUE
    return f"{value:.{decimals}f}".replace(".", ",")


def _sex(value: Optional[str]) -> str:
    return _SEX_PT.get(value, value) if value else "—"


def _sport(value: str) -> str:
    return _SPORT_PT.get(value, value)


def _verdict_icon(series: MetricSeries) -> str:
    """Coloured arrow combining movement and whether it is clinically good."""
    direction = series.direction()
    arrow = {"up": "↑", "down": "↓", "flat": "→"}[direction]
    verdict = series.verdict()
    light = {"good": "🟢", "bad": "🔴", "flat": "⬜", "neutral": "⬜"}[verdict]
    return f"{light} {arrow}"


class LongitudinalPresenter:
    """Self-contained Markdown renderer for the longitudinal/anamnesis report."""

    def __init__(self, include_metadata: bool = True):
        self._include_metadata = include_metadata

    def render(self, report: LongitudinalReport) -> str:
        parts: List[str] = []
        if self._include_metadata:
            parts.append(self._frontmatter(report))
        parts.append(self._header(report))
        parts.append(self._panel(report))
        parts.append(self._red_flags(report))
        parts.append(self._legend(report))
        parts.append(self._profile(report))
        parts.append(self._cardiovascular(report))
        parts.append(self._respiratory(report))
        parts.append(self._aerobic(report))
        parts.append(self._load(report))
        parts.append(self._recovery(report))
        parts.append(self._body_composition(report))
        parts.append(self._volume(report))
        parts.append(self._clinical_history())
        parts.append(self._provenance(report))
        return "\n".join(p for p in parts if p).rstrip() + "\n"

    def _clinical_history(self) -> str:
        """Pre-participation items a device cannot capture — to be filled by the
        clinician. Makes the report flag what it does NOT know, rather than
        implying device telemetry is sufficient for clearance."""
        return (
            "\n## 8. História clínica — a completar pelo médico\n\n"
            "Itens essenciais de uma avaliação pré-participação que **não são "
            "capturáveis por dispositivo** e devem ser coletados na consulta "
            "(especialmente por se tratar de prova de montanha, em altitude, com "
            "esforço prolongado):\n\n"
            "- **Risco cardiovascular:** história pessoal/familiar de morte súbita "
            "cardíaca, síncope, dor torácica, palpitações, hipertensão; ECG/eco se "
            "indicado.\n"
            "- **Sintomas de esforço:** dispneia desproporcional, dor torácica, "
            "tontura, claudicação.\n"
            "- **Medicações e suplementos**, alergias, infecções recentes "
            "(ex.: pós-viral), vacinação.\n"
            "- **Lesões/cirurgias prévias** e queixas musculoesqueléticas atuais.\n"
            "- **Nutrição e GI:** estratégia de hidratação/combustível, tolerância "
            "gastrointestinal em esforço longo, história alimentar (triagem de RED-S).\n"
            "- **Aclimatação a calor/altitude** e plano de exposição antes da prova "
            "(Campos do Jordão ~1.600–1.900 m).\n"
            "- **FC máxima real e zonas** (idealmente com cinta/teste) para "
            "contextualizar FC de repouso e VFC ópticas.\n"
            "- **Carga subjetiva:** percepção de fadiga, humor, motivação, qualidade "
            "de sono relatada.\n"
        )

    # -- header / panel ----------------------------------------------------- #

    def _frontmatter(self, r: LongitudinalReport) -> str:
        return (
            "---\n"
            "report_type: anamnese_longitudinal\n"
            f"generated: {r.generated_at.isoformat()}\n"
            f"period_start: {r.period_start}\n"
            f"period_end: {r.period_end}\n"
            f"athlete: {r.athlete.name or ''}\n"
            f"race: {r.targets.race_name or ''}\n"
            f"race_date: {r.targets.race_date or ''}\n"
            "data_source: garmin_connect\n"
            "data_caveat: valores são estimativas de dispositivo (triagem, não diagnóstico); sem dados de potência\n"
            "---\n"
        )

    def _header(self, r: LongitudinalReport) -> str:
        a = r.athlete
        who = a.name or "Atleta"
        bits = []
        if a.age:
            bits.append(f"{a.age} anos")
        if a.sex:
            bits.append(_sex(a.sex))
        if a.height_m:
            bits.append(f"{_num(a.height_m, 2)} m")
        demo = " · ".join(bits)
        race = r.targets.race_name or "prova-alvo"
        weeks = ""
        if r.weeks_to_race is not None:
            weeks = f" · **{r.weeks_to_race} semanas** para a prova"
            if r.days_to_race is not None:
                weeks += f" ({r.days_to_race} dias)"
        return (
            f"# 🩺 Anamnese esportiva — visão longitudinal {r.period_start} a {r.period_end}\n\n"
            f"**{who}**" + (f" · {demo}" if demo else "") + "  \n"
            f"Prova-alvo: **{race}**"
            + (f" ({r.targets.race_date})" if r.targets.race_date else "")
            + weeks + "  \n"
            f"Gerado em {r.generated_at:%d/%m/%Y} a partir do Garmin Connect.\n\n"
            f"**Veredito geral:** {r.readiness_light} {r.readiness_label}\n"
        )

    def _panel(self, r: LongitudinalReport) -> str:
        """Executive snapshot: current value vs personal baseline vs direction."""
        rows = [
            "\n## Painel clínico (resumo)\n",
            "| Métrica | Atual | Base pessoal | Tendência | Série "
            f"({r.period_start.year}→{r.period_end.year}) |",
            "|---|---|---|---|---|",
        ]
        order = [
            ("rhr", 0), ("hrv", 0), ("vo2max_cycling", 0), ("vo2max_running", 0),
            ("ctl", 0), ("weight", 1), ("sleep", 1), ("sleep_score", 0),
            ("stress", 0), ("body_battery", 0), ("spo2", 1), ("respiracao", 1),
        ]
        for key, dec in order:
            s = r.series.get(key)
            if not s or not s.values:
                continue
            base = self._baseline_cell(s)
            # Weight uses the single robust current value (median of recent
            # weigh-ins) everywhere, so the panel, section 6 and the W·kg math
            # never show three slightly different "current" weights.
            current = r.current_weight if key == "weight" else s.current
            rows.append(
                f"| {s.label} | {_num(current, dec)} {s.unit}".rstrip()
                + f" | {base} | {_verdict_icon(s)} | `{s.sparkline()}` |"
            )
        # Training load current snapshot
        if r.current_load:
            cl = r.current_load
            rows.append(
                f"| Forma atual (TSB) | {_num(cl.tsb, 0)} | CTL {_num(cl.ctl, 0)} / "
                f"ATL {_num(cl.atl, 0)} | — | — |"
            )
        return "\n".join(rows) + "\n"

    @staticmethod
    def _baseline_cell(s: MetricSeries) -> str:
        if s.baseline is None:
            return _NO_VALUE
        if s.baseline_low is not None and s.baseline_high is not None:
            return (f"{_num(s.baseline, s.decimals)} "
                    f"({_num(s.baseline_low, s.decimals)}–"
                    f"{_num(s.baseline_high, s.decimals)})")
        return _num(s.baseline, s.decimals)

    def _red_flags(self, r: LongitudinalReport) -> str:
        if not r.red_flags:
            return ("\n## 🚩 Sinais de alerta\n\n"
                    "Nenhum sinal fora de faixa no período. Métricas dentro das "
                    "bandas pessoais habituais.\n")
        lines = ["\n## 🚩 Sinais de alerta (triagem — ordenados por prioridade)\n"]
        for f in r.red_flags:
            lines.append(f"### {f.icon} {f.title}\n")
            lines.append(f"- **Achado:** {f.finding}")
            lines.append(f"- **Interpretação:** {f.detail}")
            lines.append(f"- **Conduta sugerida:** {f.recommendation}\n")
        return "\n".join(lines) + "\n"

    def _legend(self, r: LongitudinalReport) -> str:
        return (
            "\n> **Como ler:** 🟢 dentro/ favorável · 🟡 vigiar · 🔴 desfavorável · "
            "⬜ estável/neutro. Setas (↑↓→) indicam o movimento da métrica; a cor "
            "indica se esse movimento é clinicamente bom ou ruim. As sparklines `▁▂▃▅▇` "
            f"vão do início de {r.period_start.year} ao mês atual. Todos os valores são "
            "**estimativas de dispositivo de pulso** (ver Procedência).\n"
        )

    # -- domain sections ---------------------------------------------------- #

    def _profile(self, r: LongitudinalReport) -> str:
        a = r.athlete
        yt = r.year_totals
        lines = ["\n## 1. Perfil e contexto de treino\n"]
        lines.append(f"- **Atleta:** {a.name or '—'}"
                     + (f", {a.age} anos" if a.age else "")
                     + (f", {_sex(a.sex)}" if a.sex else ""))
        if a.height_m:
            bmi = f" · IMC {_num(a.bmi, 1)}" if a.bmi else ""
            lines.append(f"- **Antropometria:** {_num(a.height_m, 2)} m · "
                         f"{_num(a.weight_kg, 1)} kg{bmi} "
                         "(peso = mediana das pesagens recentes)")
        lines.append("- **Esporte principal:** ciclismo (foco), corrida e força como "
                     "complemento")
        lines.append(f"- **Prova-alvo:** {r.targets.race_name or '—'}"
                     + (f" em {r.targets.race_date}" if r.targets.race_date else "")
                     + (f" — gran fondo de montanha; **{r.weeks_to_race} semanas** a partir desta data"
                        if r.weeks_to_race is not None else ""))
        if r.current_load:
            lines.append(f"- **Carga atual:** CTL (fitness) {_num(r.current_load.ctl, 0)} · "
                         f"ATL (fadiga) {_num(r.current_load.atl, 0)} · "
                         f"TSB (forma) {_num(r.current_load.tsb, 0)}")
        # cumulative totals — the "total de atividades" overview
        if yt:
            lines.append("")
            lines.append("**Totais por ano (no período do relatório):**\n")
            lines.append("| Ano | Atividades | Dias ativos | Distância | Horas | Subida | Calorias |")
            lines.append("|---|---|---|---|---|---|---|")
            for y in yt:
                lines.append(
                    f"| {y.year} | {y.activities} | {y.days_active} | "
                    f"{_num(y.distance_km, 0)} km | {_num(y.hours, 0)} h | "
                    f"{_num(y.ascent_m, 0)} m | {y.calories:,} |".replace(",", "."))
        return "\n".join(lines) + "\n"

    def _cardiovascular(self, r: LongitudinalReport) -> str:
        lines = ["\n## 2. Cardiovascular / autonômico\n"]
        lines.append(
            "Janela longitudinal mais sensível para equilíbrio autonômico e "
            "recuperação. FC de repouso e VFC interpretadas contra a **base "
            "pessoal**, não contra a população.\n")
        for key in ("rhr", "hrv", "stress"):
            lines.append(self._metric_summary_line(r.series.get(key)))
        lines.append("")
        weekly = r.series.get("hrv_weekly")
        cols = [("FC rep. (bpm)", r.series.get("rhr"), 0),
                ("VFC noturna (ms)", r.series.get("hrv"), 0),
                ("Estresse", r.series.get("stress"), 0)]
        if weekly and weekly.values:
            cols.insert(2, ("VFC média semanal (ms)", weekly, 0))
        lines.append(self._months_table(r, cols))
        hrv = r.series.get("hrv")
        if hrv and hrv.note:
            lines.append(f"\n_{hrv.note}._")
        if r.hrv_status_latest:
            extra = ""
            if r.hrv_status_balanced_pct is not None:
                extra = (f" · {r.hrv_status_balanced_pct:.0f}% dos últimos 30 "
                         "dias em equilíbrio")
            lines.append(
                f"\n- **Status VFC (Garmin):** {r.hrv_status_latest}{extra}. "
                "Categoria do próprio Garmin; os limites de referência do "
                "fabricante (baseline_low/high) vêm de um algoritmo interno "
                "cuja faixa não contém a própria média da VFC noturna exibida "
                "acima — por isso não são plotados como faixa.")
        return "\n".join(lines) + "\n"

    def _respiratory(self, r: LongitudinalReport) -> str:
        """SpO2 + resting respiration. Numbered 2b to avoid renumbering the
        existing 1-8 sections. Renders nothing when both series are empty."""
        spo2 = r.series.get("spo2")
        rr = r.series.get("respiracao")
        cols = []
        if spo2 and spo2.values:
            cols.append(("SpO2 (%)", spo2, 1))
        if rr and rr.values:
            cols.append(("FR repouso (rpm)", rr, 1))
        if not cols:
            return ""
        lines = ["\n## 2b. Respiratório / aclimatação a altitude\n"]
        lines.append(
            "SpO2 (saturação periférica de O2) e frequência respiratória de "
            "repouso ajudam a triar tolerância a altitude e carga "
            "respiratória/estresse. Estimativas ópticas de pulso — triagem, "
            "não oximetria clínica.\n")
        for _, s, _ in cols:
            lines.append(self._metric_summary_line(s))
        lines.append("")
        lines.append(self._months_table(r, cols))
        for _, s, _ in cols:
            if s.note:
                lines.append(f"\n_{s.note}._")
        return "\n".join(lines) + "\n"

    def _aerobic(self, r: LongitudinalReport) -> str:
        lines = ["\n## 3. Aptidão aeróbica / performance\n"]
        lines.append(
            "Confirma adaptação ao treino e serve de eixo objetivo para "
            "interpretar a fadiga. VO2max é **estimativa do Garmin** (tendência, "
            "não precisão).\n")
        for key in ("vo2max_cycling", "vo2max_running", "anaerobic_te"):
            lines.append(self._metric_summary_line(r.series.get(key)))
        lines.append("")
        lines.append(self._months_table(
            r,
            [("VO2max ciclismo", r.series.get("vo2max_cycling"), 0),
             ("VO2max corrida", r.series.get("vo2max_running"), 0),
             ("TE anaeróbico", r.series.get("anaerobic_te"), 1)],
        ))
        te = r.series.get("anaerobic_te")
        if te and te.note:
            lines.append(f"\n_{te.note}._")
        lines.append("\n_Cada célula mensal é a **melhor** estimativa (máximo) do mês "
                     "(o Garmin emite uma estimativa por atividade); '—' = sem leitura "
                     "no mês. As demais séries do relatório usam médias mensais._")
        lines.append(self._power_caveat(r))
        return "\n".join(lines) + "\n"

    def _power_caveat(self, r: LongitudinalReport) -> str:
        t = r.targets
        wkg = None
        if t.ftp_watts and r.current_weight:
            wkg = t.ftp_watts / r.current_weight
        body = [
            "\n### Potência (FTP / W·kg) — somente metas configuradas\n",
            "> ⚠️ **Não há dados de potência** nas bases (nenhum medidor sincronizou "
            "watts). Os números abaixo são **metas configuradas pelo atleta**, não "
            "medições, e não podem ser verificados a partir destes dados.\n",
        ]
        if t.ftp_watts:
            body.append(f"- FTP configurado: **{_num(t.ftp_watts, 0)} W** "
                        "(autorrelato / teste externo)")
        if wkg:
            body.append(f"- W·kg estimado = FTP configurado ÷ peso atual "
                        f"({_num(r.current_weight, 1)} kg) = **{_num(wkg, 2)} W/kg** "
                        f"(meta {_num(t.wkg_target, 1)})")
        if t.weight_target_kg:
            body.append(f"- Peso-alvo de prova: {_num(t.weight_target_kg, 0)} kg")
        body.append("\nPara potência real, registrar com medidor (pedal/cubo) ou teste "
                    "laboratorial; VO2max acima é a melhor proxy disponível aqui.")
        return "\n".join(body)

    def _load(self, r: LongitudinalReport) -> str:
        lines = ["\n## 4. Carga de treino, periodização e segurança da rampa\n"]
        lines.append(
            "CTL = fitness (carga crônica 42d), ATL = fadiga (aguda 7d), "
            "TSB = forma (CTL−ATL). Carga derivada do `training_load` do Garmin "
            "(proxy de TSS; sem potência).\n")
        ctl = r.series.get("ctl")
        if ctl:
            lines.append(self._metric_summary_line(ctl))
        flags = []
        if r.acwr is not None:
            flags.append(f"- **ACWR (7d:28d):** {_num(r.acwr, 2)} "
                         "(faixa de menor risco 0,8–1,3)")
        if r.monotony is not None:
            flags.append(f"- **Monotonia (28d):** {_num(r.monotony, 2)} "
                         "(>2,0 = monótono)")
        if r.ctl_ramp_per_week is not None:
            flags.append(f"- **Rampa de CTL:** {_num(r.ctl_ramp_per_week, 1)}/semana "
                         "(guia ~3–8)")
        # Only meaningful when there is actually load data; otherwise a "100%
        # device-measured" line would falsely reassure about an empty section.
        if r.load and r.confidence_score is not None:
            flags.append(f"- **Confiança da carga:** "
                         f"{r.confidence_score * 100:.0f}% medida pelo dispositivo")
        if flags:
            lines.append("")
            lines.extend(flags)
        # The current month is partial when generated mid-month; CTL decay here
        # is a deload artefact, not detraining -- say so next to the table.
        if r.current_month_partial and r.current_load is not None:
            lines.append(
                f"\n> ℹ️ O mês atual está incompleto (dados até {r.period_end}). "
                "A queda recente de CTL reflete uma semana de baixo volume/descarga, "
                "não destreino — ACWR, rampa e monotonia acima estão em faixa segura, "
                "e o fitness deve reconstruir na fase de build.")
        lines.append("")
        lines.append(self._load_table(r))
        return "\n".join(lines) + "\n"

    def _recovery(self, r: LongitudinalReport) -> str:
        lines = ["\n## 5. Recuperação: sono e Body Battery\n"]
        lines.append(
            "Sono é o principal substrato de recuperação; o teto de Body Battery "
            "integra carga e recuperação num único proxy de reserva energética.\n")
        for key in ("sleep", "sleep_score", "body_battery"):
            lines.append(self._metric_summary_line(r.series.get(key)))
        lines.append("")
        lines.append(self._months_table(
            r,
            [("Sono (h)", r.series.get("sleep"), 1),
             ("Pont. sono", r.series.get("sleep_score"), 0),
             ("BB pico", r.series.get("body_battery"), 0)],
        ))
        return "\n".join(lines) + "\n"

    def _body_composition(self, r: LongitudinalReport) -> str:
        lines = ["\n## 6. Composição corporal / triagem de disponibilidade energética\n"]
        lines.append(
            "Triagem de RED-S (baixa disponibilidade energética): perda rápida ou "
            "sustentada de peso sob alta carga é o principal sinal de alerta.\n")
        w = r.series.get("weight")
        cur = r.current_weight
        if w and w.values:
            lines.append(
                f"- **Peso atual:** {_num(cur, 1)} kg (mediana das pesagens "
                f"recentes) · base {self._baseline_cell(w)} · faixa "
                f"{_num(w.minimum, 1)}–{_num(w.maximum, 1)} kg `{w.sparkline()}`")
            if w.first is not None and cur is not None:
                delta = cur - w.first
                pct = delta / w.first * 100 if w.first else 0.0
                sign = "+" if delta >= 0 else "−"
                lines.append(f"- Variação no período: {_num(w.first, 1)} → "
                             f"{_num(cur, 1)} kg ({sign}{_num(abs(delta), 1)} kg, "
                             f"{_num(pct, 1)}%)")
            if r.athlete.bmi:
                lines.append(f"- IMC atual ~{_num(r.athlete.bmi, 1)} "
                             f"(peso {_num(cur, 1)} kg / altura "
                             f"{_num(r.athlete.height_m, 2)} m)")
            if w.note:
                lines.append(f"- _{w.note}_")
        lines.append("")
        lines.append(self._months_table(r, [("Peso (kg)", w, 1)]))
        return "\n".join(lines) + "\n"

    def _volume(self, r: LongitudinalReport) -> str:
        lines = ["\n## 7. Volume de treino e totais\n"]
        lines.append(
            "Visão de periodização: volume mês a mês e divisão por esporte. "
            "Permite ver a construção rumo à prova, picos e quedas.\n")
        # by-sport per year
        for year in sorted(r.sport_totals_by_year):
            lines.append(f"\n**Por esporte — {year}:**\n")
            lines.append("| Esporte | Atividades | Distância | Horas | Subida |")
            lines.append("|---|---|---|---|---|")
            for s in r.sport_totals_by_year[year]:
                lines.append(
                    f"| {_sport(s.sport)} | {s.count} | {_num(s.distance_km, 0)} km | "
                    f"{_num(s.hours, 1)} h | {_num(s.ascent_m, 0)} m |")
        # monthly volume
        lines.append("\n**Volume mensal:**\n")
        lines.append("| Mês | Ativ. | Distância | Horas | Subida | Carga | TE médio |")
        lines.append("|---|---|---|---|---|---|---|")
        for v in r.volume:
            lines.append(
                f"| {v.ym} | {v.activities} | {_num(v.distance_km, 0)} km | "
                f"{_num(v.hours, 1)} h | {_num(v.ascent_m, 0)} m | "
                f"{_num(v.load_sum, 0)} | {_num(v.te_avg, 2)} |")
        # sparkline of monthly distance
        dist_spark = _spark([v.distance_km for v in r.volume])
        hours_spark = _spark([v.hours for v in r.volume])
        lines.append(f"\nDistância mensal: `{dist_spark}` · Horas mensais: `{hours_spark}`")
        return "\n".join(lines) + "\n"

    def _provenance(self, r: LongitudinalReport) -> str:
        return (
            "\n## Procedência e limitações dos dados\n\n"
            "- **Estimativas de dispositivo, não diagnóstico.** VO2max, status de VFC, "
            "estresse e Body Battery são estimativas do sensor óptico de pulso Garmin "
            "(não CPET laboratorial, ECG ou chest-strap). Use como **triagem/tendência**; "
            "confirmar com exames quando um sinal justificar.\n"
            "- **Sem dados de potência.** Nenhuma atividade registrou watts; FTP e W·kg são "
            "metas configuradas, não medições.\n"
            "- **VFC** = média noturna (rMSSD) do `monitoring_hrv_status`; a tabela `hrv` "
            "está vazia.\n"
            "- **Peso** é esparso (pesagens irregulares) — tendência direcional, não granular.\n"
            "- **CTL/ATL/TSB** usam o `training_load` do Garmin como proxy de TSS, com EWMA "
            "de 42/7 dias (mesma definição dos demais relatórios).\n"
            "- **Confundidores** (álcool, doença, calor, viagem, altitude) afetam FC de "
            "repouso, VFC e sono — interpretar sinais isolados com cautela.\n"
            "- Datas/horas já estão no **horário local** do atleta "
            f"({r.athlete.timezone or 'America/Sao_Paulo'}) — convertidas de UTC na "
            "importação — então o agrupamento mensal é por dia-calendário local.\n"
            "- **SpO2 e frequência respiratória** são estimativas do sensor "
            "óptico de pulso (Pulse Ox / respiração), não oximetria/capnografia "
            "clínica — usar para tendência e triagem de altitude, não diagnóstico.\n"
            "- **Este relatório é um resumo de telemetria longitudinal, não uma anamnese "
            "completa.** Ele não substitui a história clínica coletada pelo médico "
            "(ver seção 8).\n"
        )

    # -- shared table/line builders ---------------------------------------- #

    def _metric_summary_line(self, s: Optional[MetricSeries]) -> str:
        if s is None or not s.values:
            return ""
        return (
            f"- **{s.label}** {_verdict_icon(s)} — atual {_num(s.current, s.decimals)} "
            f"{s.unit}".rstrip()
            + f", base {self._baseline_cell(s)}, "
            f"faixa {_num(s.minimum, s.decimals)}–{_num(s.maximum, s.decimals)} "
            f"`{s.sparkline()}`"
        )

    def _months_table(
        self,
        r: LongitudinalReport,
        columns: List[Tuple[str, Optional[MetricSeries], int]],
    ) -> str:
        """Months-as-rows table; one column per metric series."""
        columns = [(h, s, d) for (h, s, d) in columns if s is not None]
        if not columns:
            return ""
        month_keys = [ym for ym, _ in (columns[0][1].points)]
        header = "| Mês | " + " | ".join(h for h, _, _ in columns) + " |"
        sep = "|---|" + "|".join("---" for _ in columns) + "|"
        lines = [header, sep]
        lookup = [
            (dict(s.points), d) for _, s, d in columns
        ]
        for ym in month_keys:
            cells = [_num(pts.get(ym), d) for pts, d in lookup]
            lines.append(f"| {ym} | " + " | ".join(cells) + " |")
        return "\n".join(lines)

    def _load_table(self, r: LongitudinalReport) -> str:
        if not r.volume and not r.load:
            return ""
        load_by_ym: Dict[str, TrainingLoadMonth] = {m.ym: m for m in r.load}
        vol_by_ym: Dict[str, VolumeMonth] = {v.ym: v for v in r.volume}
        keys = [v.ym for v in r.volume] or list(load_by_ym)
        lines = [
            "| Mês | CTL | ATL | TSB | Carga total | Horas |",
            "|---|---|---|---|---|---|",
        ]
        for ym in keys:
            lm = load_by_ym.get(ym)
            vm = vol_by_ym.get(ym)
            lines.append(
                f"| {ym} | {_num(lm.ctl if lm else None, 0)} | "
                f"{_num(lm.atl if lm else None, 0)} | "
                f"{_num(lm.tsb if lm else None, 0)} | "
                f"{_num(vm.load_sum if vm else None, 0)} | "
                f"{_num(vm.hours if vm else None, 1)} |")
        return "\n".join(lines)


def _spark(values) -> str:
    from garmindb.analysis.longitudinal_report import _sparkline
    return _sparkline(values)
