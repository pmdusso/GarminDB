# Catálogo de dados GarminDB — por domínio × grão

_Data dictionary para o sistema a jusante desenhar segmentos/agregações coerentes._
_Complementa [de-para-garmin-connect-vs-banco.md](de-para-garmin-connect-vs-banco.md) (que é análise de lacunas); este aqui é o mapa físico dos dados que **temos**._

**Fonte:** inspeção direta de `~/HealthData/DBs/` (dados reais, 2026-07-07).
**Cobertura:** diário de 2019-12-31 a 2026-07-05; atividades desde ~2020.

---

## Como ler este catálogo (leia antes de agregar)

**A "escada de grãos".** Quase toda métrica existe em mais de um grão. Escolha o mais alto que já responde a pergunta — não re-agregue de baixo se o rollup já existe.

```
série intradiária  →  por-evento/atividade  →  diário  →  semanal  →  mensal  →  anual
(monitoring_*, stress,    (activities, sleep,      (daily_summary,   (weeks_    (months_  (years_
 activity_records)         activity_laps)           days_summary)     summary)   summary)  summary)
```

**Três regras que evitam a maior parte da confusão:**

1. **Os rollups já existem e estão prontos.** `garmin_summary.db` traz `days_summary`, `weeks_summary`, `months_summary`, `years_summary` com **colunas idênticas** entre si. Se você precisa de "média semanal/mensal/anual" de qualquer métrica diária, ela já está calculada — não some `daily_summary` você mesmo. Coluna de rollup indicada na última coluna de cada tabela abaixo.

2. **`daily_summary` ≠ `days_summary`.** São dois grãos diários diferentes:
   - `garmin.daily_summary` = **registro diário de origem** (um valor por dia, baixado do Garmin). Ex.: `rhr`, `steps`, `hr_min/hr_max`.
   - `garmin_summary.days_summary` = **agregado diário derivado** (gerado pelo `--analyze` a partir das séries), com `avg/min/max`. Ex.: `hr_avg/hr_min/hr_max`, `rhr_avg/rhr_min/rhr_max`. É mais rico para estatística (tem `avg`, que o `daily_summary` às vezes não tem).
   - Regra prática: para **valor oficial do dia** use `daily_summary`; para **estatística/tendência** use `days_summary` e os rollups.

3. **⚠️ Timestamps são LOCAIS (não UTC).** O pipeline converte para hora local antes de gravar (`monitoring_hr` termina em `23:59:59` do dia local; código usa `utc_datetime_to_local`). Colunas `timestamp`/`start`/`end` estão no fuso local do usuário (São Paulo, UTC-3). **Não reconverta.** Colunas `day`/`first_day` são datas (meia-noite local).

**Legenda das colunas das tabelas:**

- **grão** — cadência do registro.
- **db.tabela** — banco + tabela.
- **tempo / chave** — coluna temporal e chave primária.
- **colunas de valor** — o que consumir.
- **linhas** — cardinalidade atual (densidade).
- **rollup pronto** — onde a versão semanal/mensal/anual já existe (`*_summary` = days/weeks/months/years_summary).

---

## 1. Cardiovascular (FC)

| métrica                  | grão           | db.tabela                            | tempo / chave                      | colunas de valor                                   | linhas | rollup pronto                    |
| ------------------------ | -------------- | ------------------------------------ | ---------------------------------- | -------------------------------------------------- | ------ | -------------------------------- |
| Frequência cardíaca      | série (~2 min) | `garmin_monitoring.monitoring_hr`    | `timestamp` / `timestamp`          | `heart_rate`                                       | 1.45M  | `*_summary.hr_avg/hr_min/hr_max` |
| FC durante intensidade   | série          | `garmin_summary.intensity_hr`        | `timestamp` / `timestamp`          | `intensity`, `heart_rate`                          | 237k   | —                                |
| FC diária (min/max)      | diário         | `garmin.daily_summary`               | `day` / `day`                      | `hr_min`, `hr_max`, `rhr`                          | 2.4k   | `*_summary.hr_*`                 |
| FC diária (avg/min/max)  | diário         | `garmin_summary.days_summary`        | `day` / `day`                      | `hr_avg/min/max`, `inactive_hr_avg/min/max`        | 1.6k   | `weeks/months/years_summary`     |
| FC de repouso (RHR)      | diário         | `garmin.resting_hr`                  | `day` / `day`                      | `resting_heart_rate`                               | 1.3k   | `*_summary.rhr_avg/min/max`      |
| FC por atividade + zonas | por-atividade  | `garmin_activities.activities`       | `start_time` / `activity_id`       | `avg_hr`, `max_hr`, `hrz_1..5_hr`, `hrz_1..5_time` | 1.2k   | —                                |
| FC por volta             | por-lap        | `garmin_activities.activity_laps`    | `start_time` / `activity_id+lap`   | `avg_hr`, `max_hr`                                 | 14.8k  | —                                |
| FC ponto-a-ponto         | série (1s)     | `garmin_activities.activity_records` | `timestamp` / `activity_id+record` | `hr`                                               | 4.85M  | —                                |

## 2. Sono

| métrica         | grão       | db.tabela             | tempo / chave                | colunas de valor                                                                                                           | linhas | rollup pronto                                          |
| --------------- | ---------- | --------------------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------------------------------ |
| Sono (noite)    | por-noite  | `garmin.sleep`        | `day` / `day`; `start`,`end` | `total_sleep`, `deep_sleep`, `light_sleep`, `rem_sleep`, `awake`, `score`, `qualifier`, `avg_spo2`, `avg_rr`, `avg_stress` | 2.4k   | `*_summary.sleep_avg/min/max`, `rem_sleep_avg/min/max` |
| Eventos de sono | por-evento | `garmin.sleep_events` | `timestamp` / `timestamp`    | `event`, `duration`                                                                                                        | 8.1k   | —                                                      |

## 3. Stress & Recuperação (stress, Body Battery, HRV)

| métrica              | grão                 | db.tabela                                 | tempo / chave             | colunas de valor                                                                                     | linhas | rollup pronto                  |
| -------------------- | -------------------- | ----------------------------------------- | ------------------------- | ---------------------------------------------------------------------------------------------------- | ------ | ------------------------------ |
| Estresse             | série (~3 min)       | `garmin.stress`                           | `timestamp` / `timestamp` | `stress`                                                                                             | 1.95M  | `*_summary.stress_avg`         |
| Estresse (média dia) | diário               | `garmin.daily_summary`                    | `day` / `day`             | `stress_avg`                                                                                         | 2.4k   | `*_summary.stress_avg`         |
| Body Battery         | diário (só agregado) | `garmin.daily_summary`                    | `day` / `day`             | `bb_charged`, `bb_max`, `bb_min`                                                                     | 2.4k   | `*_summary.bb_charged/max/min` |
| HRV (status diário)  | diário               | `garmin.hrv`                              | `day` / `day`             | `weekly_avg`, `last_night_avg`, `last_night_5min_high`, `baseline_low`, `baseline_upper`, `status`   | 858    | —                              |
| HRV (status, série)  | série                | `garmin_monitoring.monitoring_hrv_status` | `timestamp` / `timestamp` | `weekly_average`, `last_night`, `last_night_average`, `baseline_low/high`, `status`, `reading_count` | 1.4k   | —                              |
| HRV (valor bruto)    | série                | `garmin_monitoring.monitoring_hrv_value`  | `timestamp` / `timestamp` | `hrv`                                                                                                | 110k   | —                              |

> Body Battery: **só temos o agregado do dia** (carga/máx/mín), não a curva contínua. Se o sistema a jusante quer o gráfico intradiário de BB, o dado não existe.

## 4. Respiratório (respiração, SpO₂)

| métrica                 | grão           | db.tabela                               | tempo / chave             | colunas de valor                    | linhas | rollup pronto                           |
| ----------------------- | -------------- | --------------------------------------- | ------------------------- | ----------------------------------- | ------ | --------------------------------------- |
| Frequência respiratória | série (~2 min) | `garmin_monitoring.monitoring_rr`       | `timestamp` / `timestamp` | `rr`                                | 1.49M  | `*_summary.rr_waking_avg/rr_max/rr_min` |
| Respiração (diário)     | diário         | `garmin.daily_summary`                  | `day` / `day`             | `rr_waking_avg`, `rr_max`, `rr_min` | 2.4k   | `*_summary.rr_*`                        |
| SpO₂ (oximetria)        | série          | `garmin_monitoring.monitoring_pulse_ox` | `timestamp` / `timestamp` | `pulse_ox`                          | 556k   | `*_summary.spo2_avg/spo2_min`           |
| SpO₂ (diário)           | diário         | `garmin.daily_summary`                  | `day` / `day`             | `spo2_avg`, `spo2_min`              | 2.4k   | `*_summary.spo2_*`                      |

## 5. Atividade & movimento diário (passos, andares, intensidade)

| métrica                | grão   | db.tabela                                | tempo / chave             | colunas de valor                                                                                        | linhas | rollup pronto                                |
| ---------------------- | ------ | ---------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------- | ------ | -------------------------------------------- |
| Monitoramento contínuo | série  | `garmin_monitoring.monitoring`           | `timestamp+activity_type` | `intensity`, `duration`, `distance`, `steps`, `strokes`, `cycles`, `active_calories`, `cum_active_time` | 541k   | —                                            |
| Passos (diário)        | diário | `garmin.daily_summary`                   | `day` / `day`             | `steps`, `step_goal`                                                                                    | 2.4k   | `*_summary.steps/steps_goal`                 |
| Andares                | série  | `garmin_monitoring.monitoring_climb`     | `timestamp` / `timestamp` | `ascent`, `descent`, `cum_ascent`, `cum_descent`                                                        | 51.7k  | —                                            |
| Andares (diário)       | diário | `garmin.daily_summary`                   | `day` / `day`             | `floors_up`, `floors_down`, `floors_goal`                                                               | 2.4k   | `*_summary.floors/floors_goal`               |
| Minutos de intensidade | série  | `garmin_monitoring.monitoring_intensity` | `timestamp` / `timestamp` | `moderate_activity_time`, `vigorous_activity_time`                                                      | 6.8k   | —                                            |
| Intensidade (diário)   | diário | `garmin.daily_summary`                   | `day` / `day`             | `moderate_activity_time`, `vigorous_activity_time`, `intensity_time_goal`                               | 2.4k   | `*_summary.intensity_time/moderate/vigorous` |

## 6. Exercício / Treinos (atividades)

Taxonomia: `activities.sport` + `sub_sport` (23 combinações; ver de-para). Extensões por esporte compartilham `activity_id`.

| métrica              | grão          | db.tabela                               | tempo / chave                      | colunas de valor                                                                                                                                                                                                                                                                                        | linhas        | rollup pronto                                                  |
| -------------------- | ------------- | --------------------------------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- | -------------------------------------------------------------- |
| Resumo da atividade  | por-atividade | `garmin_activities.activities`          | `start_time` / `activity_id`       | `sport`, `sub_sport`, `distance`, `elapsed_time`, `moving_time`, `avg_speed/max_speed`, `avg_hr/max_hr`, `avg_cadence/max_cadence`, `calories`, `ascent/descent`, `training_load`, `training_effect`, `anaerobic_training_effect`, `self_eval_feel/effort`, `avg/max/min_temperature`, `start_lat/long` | 1.2k          | `*_summary.activities/activities_calories/activities_distance` |
| Voltas               | por-lap       | `garmin_activities.activity_laps`       | `start_time` / `activity_id+lap`   | mesmo conjunto de `activities` por volta                                                                                                                                                                                                                                                                | 14.8k         | —                                                              |
| Série ponto-a-ponto  | série (1s)    | `garmin_activities.activity_records`    | `timestamp` / `activity_id+record` | `position_lat/long`, `distance`, `altitude`, `speed`, `hr`, `cadence`, `power`, `rr`, `temperature`                                                                                                                                                                                                     | 4.85M         | —                                                              |
| Extensão corrida     | por-atividade | `garmin_activities.steps_activities`    | — / `activity_id`                  | `steps`, `avg_pace/max_pace`, `avg_step_length`, `avg_vertical_oscillation/ratio`, `avg_ground_contact_time`, `avg_gct_balance`, `avg_steps_per_min`, `vo2_max`                                                                                                                                         | 221           | —                                                              |
| Extensão ciclismo    | por-atividade | `garmin_activities.cycle_activities`    | — / `activity_id`                  | `strokes`, `vo2_max`                                                                                                                                                                                                                                                                                    | 754           | —                                                              |
| Extensão remo/paddle | por-atividade | `garmin_activities.paddle_activities`   | — / `activity_id`                  | `strokes`, `avg_stroke_distance`                                                                                                                                                                                                                                                                        | 5             | —                                                              |
| Splits               | por-split     | `garmin_activities.activity_splits`     | — / `activity_id+split`            | (mesmo conjunto de laps)                                                                                                                                                                                                                                                                                | **0 (vazia)** | —                                                              |
| Escalada             | por-atividade | `garmin_activities.climbing_activities` | — / `activity_id`                  | `total_routes`                                                                                                                                                                                                                                                                                          | **0 (vazia)** | —                                                              |

> `power` em `activity_records` está populado para ciclismo **e** corrida (potência nativa Stryd). Permite derivar Curva de Potência / NP / TSS — não há tabela pronta.

## 7. Composição corporal

| métrica | grão               | db.tabela       | tempo / chave | colunas de valor | linhas | rollup pronto                  |
| ------- | ------------------ | --------------- | ------------- | ---------------- | ------ | ------------------------------ |
| Peso    | por-medição/diário | `garmin.weight` | `day` / `day` | `weight`         | 417    | `*_summary.weight_avg/min/max` |

## 8. Nutrição & Hidratação

| métrica    | grão   | db.tabela              | tempo / chave | colunas de valor                                                                          | linhas | rollup pronto                                                    |
| ---------- | ------ | ---------------------- | ------------- | ----------------------------------------------------------------------------------------- | ------ | ---------------------------------------------------------------- |
| Calorias   | diário | `garmin.daily_summary` | `day` / `day` | `calories_total`, `calories_bmr`, `calories_active`, `calories_consumed`, `calories_goal` | 2.4k   | `*_summary.calories_avg/bmr_avg/active_avg/goal/consumed_avg`    |
| Hidratação | diário | `garmin.daily_summary` | `day` / `day` | `hydration_goal`, `hydration_intake`, `sweat_loss`                                        | 2.4k   | `*_summary.hydration_goal/avg/intake, sweat_loss_avg/sweat_loss` |

> Nutrição = **só totais** de calorias (sem macros/refeições).

## 9. Prontidão & Desempenho

| métrica                | grão          | db.tabela                                                 | tempo / chave                | colunas de valor                                                                                                                                                          | linhas                       | rollup pronto |
| ---------------------- | ------------- | --------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- | ------------- |
| Training Readiness     | diário        | `garmin.training_readiness`                               | `day` / `day`; `timestamp`   | `score`, `level`, `feedback_short/long`, `recovery_time`, `sleep_score`, `acwr_factor_pct`, `acute_load`, `hrv_factor_pct`, `hrv_weekly_average`, e demais `*_factor_pct` | **21** (só 2026-06-04→06-24) | —             |
| VO₂ Máx                | por-atividade | `garmin_activities.steps_activities` / `cycle_activities` | — / `activity_id`            | `vo2_max` (corrida 47–58, ciclismo 52–57)                                                                                                                                 | 221 / 754                    | —             |
| Efeito/carga de treino | por-atividade | `garmin_activities.activities`                            | `start_time` / `activity_id` | `training_effect`, `anaerobic_training_effect`, `training_load`                                                                                                           | 1.2k                         | —             |

> Não há série histórica dedicada de VO₂ Máx, Training Status, Race Predictor, FTP, limiar de lactato (ver de-para). O que existe de "desempenho" é o que está carimbado por atividade + Training Readiness (janela curta).

## 10. Dispositivos & arquivos (metadados, não-saúde)

| métrica               | grão            | db.tabela            | tempo / chave             | colunas de valor                                                              | linhas | rollup pronto |
| --------------------- | --------------- | -------------------- | ------------------------- | ----------------------------------------------------------------------------- | ------ | ------------- |
| Dispositivos          | por-dispositivo | `garmin.devices`     | — / `serial_number`       | (cadastro do dispositivo)                                                     | —      | —             |
| Estado do dispositivo | por-evento      | `garmin.device_info` | `timestamp+serial_number` | `software_version`, `battery_status`, `battery_voltage`, `cum_operating_time` | 22.5k  | —             |
| Arquivos importados   | por-arquivo     | `garmin.files`       | — / `id`                  | (proveniência dos FIT/TCX/JSON)                                               | —      | —             |

---

## Guia rápido de decisão para o agente a jusante

1. **Segmento é por dia/semana/mês/ano?** → comece em `days/weeks/months/years_summary` (`garmin_summary.db`). A coluna já existe agregada. Só desça para série se precisar de intradiário.
2. **Precisa do valor "oficial" do dia (não estatística)?** → `garmin.daily_summary`.
3. **Precisa da curva intradiária?** → tabela `monitoring_*` ou `stress` correspondente (chave `timestamp`, fuso local).
4. **Segmento é sobre treinos?** → `activities` (resumo) → `activity_laps` (volta) → `activity_records` (ponto-a-ponto). Junte extensões por `activity_id`.
5. **Junção entre domínios diários** → todos usam `day` (ou `first_day` nos rollups) como chave; junte por data.
6. **Nunca reconverta fuso** dos `timestamp` — já são locais.
7. **Grãos vazios/rasos:** `activity_splits` e `climbing_activities` estão vazias; `training_readiness` só tem 21 dias; Body Battery só diário. Trate como indisponíveis para segmentar até serem populados.
