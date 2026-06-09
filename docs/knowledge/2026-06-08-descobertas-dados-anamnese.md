#needs-peer-review

# Descobertas sobre os dados ao construir o relatório de anamnese longitudinal

**Data:** 2026-06-08

## Contexto

Construção de um relatório longitudinal 2025/2026 para uma anamnese esportiva (médico do esporte). Ao inventariar os dados reais em `~/HealthData/DBs/`, vários pressupostos implícitos nos relatórios existentes (`relatorio-performance-*.md`, `relatorio-consulta-*.md`) se mostraram falsos ou enganosos. Documentado aqui para revisão humana.

---

## 1. Não há dados de potência — FTP/W·kg são metas configuradas, não medições

- **Mito/pressuposto:** O `relatorio-performance-2026-06-08.md` exibe "FTP 325 W" e "W/kg 3,72" como se fossem métricas medidas do atleta.
- **Fato:** **Nenhuma** atividade nas bases possui dado de potência. Não existe coluna de potência em `activities` nem em `activity_records` (em nenhuma das ~1190 atividades). O valor 325 W vem de `~/.GarminDb/performance_targets.json` (`ftp_watts: 325`), e 3,72 = 325 ÷ peso. São **metas/autorrelato**, não medições verificáveis a partir do Garmin.
- **Evidência:**
  - `sqlite3 garmin_activities.db ".schema activities"` → sem coluna de potência.
  - `~/.GarminDb/performance_targets.json` → `{"ftp_watts": 325, "weight_target_kg": 80, "wkg_target": 4.0, ...}`.
  - `garmindb/analysis/performance_report.py:129` → `ftp_used = t.ftp_watts or power.estimated_ftp` (cai sempre no valor configurado, pois não há potência para estimar).
- **Implicação analítica:** Qualquer relatório clínico DEVE rotular FTP/W·kg como meta configurada e não como medição. Para potência real é preciso medidor (pedal/cubo) ou teste laboratorial. O novo relatório de anamnese faz isso explicitamente (seção 3, caixa de aviso).

## 2. `activities.distance` está em QUILÔMETROS, não metros

- **Mito/pressuposto:** Natural assumir metros (como em muitos schemas Garmin/FIT) e dividir por 1000.
- **Fato:** A coluna já está em km. Ciclismo 2025: `AVG(distance)=53,0`, `MAX=202,5`, `SUM=9956,6` — coerente com km por pedal, absurdo se fosse metros.
- **Evidência:** `SELECT AVG(distance), MAX(distance) FROM activities WHERE sport='cycling' AND start_time>='2025-01-01'` → 53,0 / 202,5. O `ActivityAnalyzer` soma `distance` direto e reporta "km", confirmando a unidade.
- **Implicação analítica:** Somar `distance` diretamente para totais em km. Dividir por 1000 produziria distâncias 1000× menores — erro grave num relatório médico. (Guardado por teste de regressão `test_distance_summed_as_km_not_meters`.)

## 3. A fonte de FC de repouso para 2026 é `daily_summary.rhr`, não a tabela `resting_hr`

- **Mito/pressuposto:** A tabela dedicada `resting_hr` seria a fonte de FC de repouso.
- **Fato:** `resting_hr` termina em 2026-01-03 (1146 linhas); está incompleta. `daily_summary.rhr` cobre todo 2025 e 2026.
- **Evidência:** `SELECT MAX(day) FROM resting_hr` → 2026-01-03; `SELECT MAX(day) FROM daily_summary` → 2026-06-07 com `rhr` preenchido.
- **Implicação analítica:** Usar `daily_summary.rhr` para qualquer série longitudinal de FC de repouso.

## 4. A tabela `hrv` está vazia; a VFC real está em `monitoring_hrv_status`

- **Mito/pressuposto:** A tabela de nome óbvio `garmin.db.hrv` conteria a série de VFC.
- **Fato:** `garmin.db.hrv` tem 0 linhas. A VFC noturna está em `garmin_monitoring.db.monitoring_hrv_status.last_night_average` (diária, 2022-10 → 2026-06).
- **Evidência:** `SELECT COUNT(*) FROM hrv` → 0; `SELECT COUNT(*) FROM monitoring_hrv_status` → 1350.
- **Nota adicional:** As colunas `baseline_low`/`baseline_high` de `monitoring_hrv_status` estão numa escala diferente (~33–40 ms) da `last_night_average` (~50–76 ms) — não usar como banda de base, pois a "base" não conteria a própria média. O relatório deriva a base pessoal da própria série.
- **Implicação analítica:** Toda tendência de VFC vem de `monitoring_hrv_status.last_night_average`.

## 5b. Os timestamps já estão em horário LOCAL, não UTC

- **Mito/pressuposto:** O `CLAUDE.md` afirma "All timestamps are UTC in the database"; um relatório chegou a imprimir "Timestamps em UTC".
- **Fato:** Os horários são gravados em **horário local** do atleta (convertidos de UTC na importação). `garmindb/activity_fit_file_processor.py` usa `fit_file.utc_datetime_to_local(...)` ao gravar `start_time`. O histograma de hora-do-dia das atividades tem pico às 06:00–09:00 (treinos matinais locais) e zero entre 00:00–03:00 — impossível se fossem UTC para um atleta em UTC−3.
- **Implicação analítica:** O agrupamento mensal por `date(start_time)` está correto (é por dia-calendário local). Mas qualquer texto de procedência deve dizer "horário local", não UTC. (Corrigido no relatório de anamnese.)

## 5. Não existem CTL/ATL/TSB nativos — são computados por EWMA do `training_load`

- **Fato:** Não há colunas de CTL/ATL/TSB nas bases. O `ActivityAnalyzer` (e o novo `LongitudinalReportBuilder`) computam EWMA de 42d/7d sobre `activities.training_load` (proxy de TSS do Garmin, não TSS de potência). `training_load` está presente em ~1010/1190 atividades.
- **Implicação analítica:** Rotular CTL/ATL/TSB como derivados do `training_load` do Garmin, não como TSS clássico de potência.

---

## Observação clínica emergente (não-dado, mas relevante)

A visão longitudinal revelou um sinal que os relatórios de janela única (30 dias / Jan–Jun) não mostravam: em **maio–início de junho 2026** convergem VFC ↓ (~70→53 ms), estresse ↑ (~29→34), teto de Body Battery ↓ (90→63) e pontuação de sono ↓ (82→73), com FC de repouso levemente elevada. É o padrão de débito de recuperação / overreaching incipiente — justamente o tipo de tendência que motiva uma anamnese longitudinal. Sinal de triagem (estimativas de pulso), a confirmar clinicamente.
