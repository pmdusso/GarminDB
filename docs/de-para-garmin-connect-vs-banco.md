# De→Para: Garmin Connect × Banco de dados GarminDB

_Mapeia cada item do menu do Garmin Connect (ver [dados-originais-garmin-connect.md](dados-originais-garmin-connect.md)) contra o que existe no banco local._

**Fonte:** inspeção direta dos DBs em `~/HealthData/DBs/` (não só schema — dados reais).
**Cobertura temporal:** diário de 2019-12-31 a 2026-07-05; atividades desde ~2020.

## Legenda

- ✅ **Temos** — dado disponível e populado.
- 🟡 **Parcial** — temos algo próximo, mas com menos granularidade/campos, ou derivado de outra fonte.
- ❌ **Não temos** — Garmin calcula/mostra, mas não é baixado para o banco.

---

## 2. Atividades

| Garmin Connect             | Status | Onde no banco                                                                                                                                                         |
| -------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Passos                     | ✅     | `garmin.daily_summary.steps` (+ meta `step_goal`); série em `garmin_monitoring.monitoring.steps`; agregados em `garmin_summary.days/weeks/months/years_summary.steps` |
| Andares (subidos/descidos) | ✅     | `daily_summary.floors_up/floors_down/floors_goal`; série em `monitoring_climb` (ascent/descent cumulativos)                                                           |
| Minutos de intensidade     | ✅     | `daily_summary.moderate_activity_time/vigorous_activity_time` (+ meta); série em `monitoring_intensity`                                                               |
| Todas as atividades        | ✅     | `garmin_activities.activities` (1210 ativs., 23 tipos de esporte)                                                                                                     |

## 3. Estatísticas de saúde

| Garmin Connect                                | Status | Onde no banco                                                                                                        |
| --------------------------------------------- | ------ | -------------------------------------------------------------------------------------------------------------------- |
| Sono                                          | ✅     | `garmin.sleep` (fases: deep/light/rem/awake, score, qualifier, spo2, rr, stress) + `sleep_events` (série de eventos) |
| Status de saúde (Health Snapshot)             | ❌     | —                                                                                                                    |
| Peso                                          | ✅     | `garmin.weight`; composição corporal oficial entra bruta em `connect_metric_raw` (`body_composition`) quando habilitada |
| Pressão sanguínea                             | ❌     | Não há tabela de pressão                                                                                             |
| Oximetria de pulso (SpO₂)                     | ✅     | `daily_summary.spo2_avg/spo2_min`; série minuto-a-minuto em `monitoring_pulse_ox` (556k linhas)                      |
| Aclimatação com oximetria (altitude)          | ❌     | —                                                                                                                    |
| Respiração (freq. respiratória)               | ✅     | `daily_summary.rr_waking_avg/rr_max/rr_min`; série em `monitoring_rr` (1.5M linhas); `sleep.avg_rr`                  |
| Frequência cardíaca                           | ✅     | Série em `monitoring_hr` (1.4M linhas); `daily_summary.hr_min/hr_max/rhr`; RHR dedicado em `resting_hr`              |
| Idade do condicionamento físico (Fitness Age) | 🟡     | Suporte de import bruto em `connect_metric_raw` (`fitness_age`); ainda sem tabela analítica normalizada             |
| Estresse                                      | ✅     | `garmin.stress` (série, 1.95M linhas); `daily_summary.stress_avg`                                                    |
| Body Battery                                  | 🟡     | Agregado diário em `daily_summary.bb_charged/bb_max/bb_min`; payload oficial detalhado passa por `connect_metric_raw` quando `body_battery` estiver habilitado |
| Resumo de saúde                               | ✅     | `garmin_summary.days_summary` (linha por dia com HR, sono, estresse, peso, calorias, SpO₂, RR, BB…)                  |

## 4. Nutrição

| Garmin Connect      | Status | Onde no banco                                                                                                            |
| ------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------ |
| Nutrição / calorias | 🟡     | `daily_summary.calories_consumed` (só total ingerido; **sem macros/refeições**). Também `calories_total/bmr/active/goal` |
| Hidratação          | ✅     | `daily_summary.hydration_goal/hydration_intake/sweat_loss`                                                               |

## 5. Estatísticas de desempenho

| Garmin Connect                        | Status | Onde no banco                                                                                                                                                                    |
| ------------------------------------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Status de treinamento                 | 🟡     | Suporte de import bruto em `connect_metric_raw` (`training_status`); ainda sem tabela analítica normalizada                                                                      |
| Disposição / autoavaliação            | 🟡     | Por atividade: `activities.self_eval_feel/self_eval_effort`. Não há série de "mood"                                                                                              |
| Status de VFC (HRV)                   | ✅     | `garmin.hrv` (diário: weekly_avg, last_night, baseline, status); `monitoring_hrv_status` (1378) + `monitoring_hrv_value` (série, 110k)                                           |
| Previsão de corrida (Race Predictor)  | 🟡     | Suporte de import bruto em `connect_metric_raw` (`running_predictions`); ainda sem tabela analítica normalizada                                                                  |
| VO₂ Máx                               | 🟡     | Só carimbado por atividade: `steps_activities.vo2_max` (corrida 47–58), `cycle_activities.vo2_max` (ciclismo 52–57). **Não** há série histórica de saúde dedicada                |
| Efeito de treino                      | ✅     | `activities.training_effect` (aeróbico) + `anaerobic_training_effect` + `training_load`                                                                                          |
| Curva de potência                     | 🟡     | Não há tabela de curva. Mas há `power` bruto em `activity_records` (série por ativ.) → dá pra **calcular** a curva                                                               |
| FTP                                   | 🟡     | Potência por atividade/rollup existe; payload oficial de limiar/FTP de corrida entra bruto em `connect_metric_raw` (`lactate_threshold`)                                         |
| Velocidade crítica de natação         | ❌     | —                                                                                                                                                                                |
| Limiar de lactato                     | 🟡     | Suporte de import bruto em `connect_metric_raw` (`lactate_threshold`); ainda sem normalização clínica                                                                            |
| Pontuação em resistência (Endurance)  | 🟡     | Suporte de import bruto em `connect_metric_raw` (`endurance_score`); ainda sem tabela analítica normalizada                                                                      |
| Pontuação em subida (Hill Score)      | 🟡     | Suporte de import bruto em `connect_metric_raw` (`hill_score`); ainda sem tabela analítica normalizada                                                                           |
| Estresse na variação da FC (HRV load) | ❌     | Temos HRV status, mas não a métrica "HRV load/stress"                                                                                                                            |
| **Training Readiness**                | ✅     | `garmin.training_readiness` (score, level, feedback, fatores de recuperação/sono/HRV/carga). ⚠️ só 21 dias (2026-06-04→06-24) — feature nova do fork, não estava no doc original |

## 6. Golfe

❌ Nada. Nenhuma tabela de golfe/scorecards.

## 7. Treinamento e Planejamento

❌ Exercícios/workouts, Planos, Percursos, Segmentos, PacePro, Guia de potência, Heatmap — nada disso é importado. `activities.course_id` existe mas não há tabela de percursos.

## 8. Equipamento

| Garmin Connect            | Status | Onde no banco                                                                  |
| ------------------------- | ------ | ------------------------------------------------------------------------------ |
| Dispositivos / acessórios | ✅     | `garmin.devices`, `device_info` (bateria, firmware, tempo de operação, serial) |

## 9. Insights

❌ Benchmarking social (você vs. outros usuários) — não é baixado.

## 12. Medalhas / Recordes / Objetivos

❌ Gamificação e metas não são importadas (só as _metas diárias_ embutidas: `step_goal`, `floors_goal`, `calories_goal`, `intensity_time_goal`, `hydration_goal`).

---

## 10. Relatórios — detalhe por atividade

Os "Relatórios" do Garmin (Ciclismo, Corrida, Natação…) são **recortes por esporte** da mesma base de atividades. No banco isso vem de `activities` + tabelas de extensão + séries em `activity_laps`/`activity_records`.

### Cobertura das métricas dos relatórios

| Métrica de relatório                                                        | Status | Coluna                                                                                                                              |
| --------------------------------------------------------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| Distância / Tempo / Velocidade / Ritmo médio                                | ✅     | `activities.distance/elapsed_time/moving_time/avg_speed/max_speed`                                                                  |
| Calorias na atividade                                                       | ✅     | `activities.calories`                                                                                                               |
| FC média / máxima                                                           | ✅     | `activities.avg_hr/max_hr` (+ zonas `hrz_1..5_hr/_time`)                                                                            |
| Cadência (corrida/bike)                                                     | ✅     | `activities.avg_cadence/max_cadence`                                                                                                |
| Subida total (ascent)                                                       | ✅     | `activities.ascent/descent`                                                                                                         |
| Potência média                                                              | 🟡     | Não há coluna resumo em `activities`; há `power` bruto por ponto em `activity_records`                                              |
| Normalized Power / TSS / IF                                                 | ❌     | Não calculados/armazenados                                                                                                          |
| Dinâmica de corrida (osc. vertical, GCT, comprimento passo, vertical ratio) | ✅     | `steps_activities.avg_vertical_oscillation/avg_ground_contact_time/avg_step_length/avg_vertical_ratio/avg_gct_balance`              |
| Braçadas / Swolf (natação)                                                  | 🟡     | `cycle_activities.strokes`, `paddle_activities.strokes/avg_stroke_distance`. **Swolf não** tem coluna dedicada                      |
| VO₂ Máx (por esporte)                                                       | 🟡     | `steps_activities.vo2_max`, `cycle_activities.vo2_max`                                                                              |
| Treino de força (reps/volume/exercícios)                                    | ❌     | Há atividades `strength_training` (174) em `activities`, mas **sem tabela de séries/reps/exercícios**. `activity_splits` está vazia |
| Temperatura                                                                 | ✅     | `activities.avg/max/min_temperature`                                                                                                |
| GPS / rota                                                                  | ✅     | `activities.start_lat/long`, `stop_lat/long`; série completa em `activity_records.position_lat/long`                                |

### Séries brutas por atividade (o mais granular que temos)

- `activity_records` (4.8M linhas): timestamp, lat/long, distância, cadência, altitude, HR, RR, speed, **power**, temperatura — ponto a ponto.
- `activity_laps` (14.8k): mesmo conjunto de métricas por volta.
- `activity_splits`: **vazia** (0 linhas) — splits automáticos não populados.

---

## Resumo executivo

**Temos bem coberto:** passos, andares, intensidade, FC (série+RHR), estresse, sono, SpO₂, respiração, peso, hidratação, HRV, atividades completas com GPS/HR/power/cadência ponto-a-ponto, efeito de treino, e agregados diário/semana/mês/ano.

**Lacunas principais (Garmin calcula, não baixamos):**

1. Métricas fisiológicas derivadas agora têm **import bruto opcional** para Fitness Age, Training Status, Race Predictor/Running Tolerance, Endurance/Hill Score e Limiar de lactato; falta normalização analítica.
2. **Body Battery** tem agregado diário e import bruto opcional da curva/eventos; falta normalização analítica.
3. **Treino de força** sem séries/reps/exercícios/músculos (o "formato especial" do doc não é capturado).
4. **Nutrição** só calorias totais (sem macros); composição corporal pode ser capturada bruta se houver dados no Garmin.
5. **Pressão sanguínea, Golfe, Planejamento/Workouts, Insights sociais, Medalhas/Objetivos** — nada.
6. `activity_splits` vazia; NP/TSS/IF e curva de potência não pré-calculados (mas `power` bruto permite derivar).

> `connect_metric_raw` é uma área privada de captura de payload oficial Garmin Connect.
> Esses JSONs não devem alimentar o payload público do BloodB sem allowlist explícita
> de campos e sem remover identificadores, textos ou metadados operacionais.
