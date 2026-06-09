"""Render a PerformanceReport to Markdown."""

import logging
from typing import List

from garmindb.analysis.performance_report import PerformanceReport, ScorecardRow

logger = logging.getLogger(__name__)

# Placeholder shown when a metric has no value (formatted by the builder).
_NO_VALUE = "—"


class PerformancePresenter:
    """Self-contained Markdown renderer for the performance report."""

    def __init__(self, include_metadata: bool = True):
        self._include_metadata = include_metadata

    def render(self, report: PerformanceReport) -> str:
        parts: List[str] = []
        if self._include_metadata:
            parts.append(self._frontmatter(report))
        parts.append(self._header(report))
        parts.append(self._readiness(report))
        parts.append(self._scorecard(report))
        parts.append(self.render_power_block(report.power, report.wkg_measured))
        parts.append(self._coverage(report))
        parts.append(self._priorities(report))
        return "\n".join(p for p in parts if p).rstrip() + "\n"

    def _frontmatter(self, r: PerformanceReport) -> str:
        return (
            "---\n"
            "report_type: performance\n"
            f"generated: {r.generated_at.isoformat()}\n"
            f"period_start: {r.period_start}\n"
            f"period_end: {r.period_end}\n"
            f"race: {r.targets.race_name or ''}\n"
            "---\n"
        )

    def _header(self, r: PerformanceReport) -> str:
        race = r.targets.race_name or "prova-alvo"
        return (
            f"# 🎯 Performance — {r.period_start} a {r.period_end}\n\n"
            f"Meta: {race}"
            + (f" ({r.targets.race_date})" if r.targets.race_date else "")
            + f" · gerado {r.generated_at:%d/%m/%Y}\n"
        )

    def _readiness(self, r: PerformanceReport) -> str:
        return f"\n**PRONTIDÃO:** {r.readiness_light} {r.readiness_label}\n"

    @staticmethod
    def _delta_cell(row: ScorecardRow) -> str:
        # No value this run: the Δ is meaningless — say so explicitly instead
        # of implying a "baseline" (which only applies on a true first run).
        if row.current == _NO_VALUE:
            return "sem dado"
        delta = row.delta
        if delta is None or not delta.has_previous:
            return "baseline"
        change = delta.delta
        arrow = "↑" if change > 0 else ("↓" if change < 0 else "→")
        return f"{arrow} {abs(change):.2f}".replace(".", ",")

    def _scorecard(self, r: PerformanceReport) -> str:
        lines = [
            "\n## Resumo Executivo\n",
            "| Métrica | Agora | Meta | Gap | Δ |",
            "|---|---|---|---|---|",
        ]
        for row in r.scorecard:
            lines.append(
                f"| {row.label} | {row.current} | {row.target} | "
                f"{row.gap} | {self._delta_cell(row)} |"
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def render_power_block(power, wkg_measured=None) -> str:
        """Measured-vs-configured power section. Renders nothing if no power."""
        if power is None or power.total_rides == 0:
            return ""

        def w(v, nd=0):
            return f"{v:.{nd}f}".replace(".", ",") if v is not None else _NO_VALUE

        lines = ["\n## Potência (medida vs configurada)\n"]
        lines.append(f"- **FTP configurado:** {w(power.configured_ftp)} W (meta)")
        if power.gate and power.gate.published and power.eftp_measured:
            src = ("outdoor" if power.eftp_source == "outdoor"
                   else "indoor (~8–12% abaixo do outdoor)")
            gap = (power.eftp_measured - power.configured_ftp
                   if power.configured_ftp else None)
            lines.append(
                f"- **eFTP medido:** {w(power.eftp_measured)} W — fonte {src}; "
                f"melhor 20-min × 0,95 ({power.gate.candidate_count} pedais, "
                "janela 6 sem). Estimativa de campo, não teste de laboratório."
                + (f" Gap vs configurado: {w(gap)} W." if gap is not None else ""))
            if wkg_measured is not None:
                lines.append(f"- **W·kg medido:** {w(wkg_measured, 2)} "
                             "(eFTP ÷ peso pareado ±7 d do esforço)")
        else:
            reason = power.gate.reason if power.gate else "sem esforço qualificado"
            lines.append(f"- **eFTP medido:** não publicado — {reason}.")
        if power.peak_5s:
            dropped = getattr(power, "peak_5s_dropped", 0) or 0
            extra = (f" {dropped} leitura(s) de 5 s descartada(s) como ruído."
                     if dropped else "")
            lines.append(f"- **Pico neuromuscular (5 s):** {w(power.peak_5s)} W "
                         "(maxAvgPower_5; nunca o pico de 1 s, que é ruído)."
                         + extra)
        if power.np_variability_ratio:
            lines.append(
                f"- **Variabilidade (NP/méd, ≥30 min):** "
                f"{w(power.np_variability_ratio, 2)} sobre "
                f"{power.np_long_ride_count} pedais (1,0 = constante).")
        # Curves (indoor/outdoor) at the key durations.
        labels = [(5, "5 s"), (60, "1 min"), (300, "5 min"),
                  (1200, "20 min"), (3600, "60 min")]
        lines.append("\n| Duração | Outdoor (W) | Indoor (W) |")
        lines.append("|---|---|---|")
        for d, lab in labels:
            lines.append(f"| {lab} | {w(power.curve_outdoor.get(d))} | "
                         f"{w(power.curve_indoor.get(d))} |")
        # Zone distribution (already computed by the analyzer; previously dropped).
        if power.power_zone_distribution:
            znames = {1: "Z1", 2: "Z2", 3: "Z3", 4: "Z4", 5: "Z5", 6: "Z6", 7: "Z7"}
            zbits = [f"{znames.get(z, z)} {p:.0f}%"
                     for z, p in sorted(power.power_zone_distribution.items())]
            lines.append("\n**Zonas de potência (% do tempo):** " + " · ".join(zbits))
        return "\n".join(lines) + "\n"

    def _coverage(self, r: PerformanceReport) -> str:
        """Disclose how much of the data backed the power numbers.

        Without this, a report built on 2 of 40 rides looks identical to a
        complete one. We surface the ride coverage, the analysed window,
        any silently-skipped files, and an explicit warning when no ride
        carried power (the meter likely was not recording).
        """
        power = r.power
        if power is None:
            logger.debug("No power block on report; skipping coverage line.")
            return ""

        line = (
            f"_Cobertura de potência: {power.total_rides} pedais com potência "
            f"no histórico; {power.recent_ride_count} nos últimos 90 dias "
            "(forma atual)"
        )
        skipped = getattr(power, "skipped_files", 0) or 0
        if skipped > 0:
            line += f"; {skipped} arquivos ilegíveis ignorados"
            logger.warning(
                "Power coverage: %d file(s) were unreadable and ignored.",
                skipped,
            )
        line += "._"

        parts = ["\n" + line]
        if power.recent_ride_count == 0 and power.total_rides > 0:
            logger.warning(
                "Power coverage: 0 of %d rides had power; meter likely "
                "was not recording.", power.total_rides,
            )
            parts.append(
                "\n> ⚠️ Nenhum pedal recente registrou potência — o "
                "medidor de potência provavelmente não estava gravando."
            )
        return "\n".join(parts) + "\n"

    def _priorities(self, r: PerformanceReport) -> str:
        if not r.priorities:
            return ""
        lines = ["\n## Prioridades agora\n"]
        for i, p in enumerate(r.priorities, 1):
            lines.append(f"{i}. {p}")
        return "\n".join(lines) + "\n"
