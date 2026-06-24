`#needs-peer-review`

# SPEC: Training Readiness — fatia vertical (download → tabela → anamnese)

**Data:** 2026-06-24 · **Status:** Design aprovado, pronto para plano de implementação
**Origem:** Fase 2 do roadmap north-star (`docs/plans/2026-06-09-roadmap-trainingpeaks-northstar.md`),
item "Training Status / Readiness" — o único item da Fase 2 genuinamente pendente
(decoupling, import de potência e tabela `hrv` já estão entregues; o roadmap está
desatualizado quanto a isso).

## Contexto e objetivo

A anamnese cobre fisiologia, carga e potência, mas **não** traz a síntese de
prontidão do próprio Garmin. O **Training Readiness** é um score matinal 0–100 que
combina sono, recuperação, VFC, histórico de stress/sono e carga aguda — alto valor
clínico e de periodização para a preparação da prova (L'Étape Campos do Jordão,
2026-09-27).

**Escopo desta SPEC:** apenas **Training Readiness** (fatia vertical completa:
download → import → tabela → render na anamnese). O **Recovery Time** está incluído
porque é um *campo* do readiness (`recoveryTime`), não um endpoint separado. O
**Training Status** (classificação productive/peaking/load balance) fica para uma
**SPEC separada** — seus dados são aninhados, indexados por `deviceId`, e parcialmente
redundantes com a anamnese (VO2max na Seção 3, aclimatação na Seção 2b).

## Viabilidade (verificada)

- Lib já instalada: `garminconnect==0.3.3` expõe `get_training_readiness(date)`.
  **Sem nova dependência.**
- **Forma real dos dados** (sondagem read-only de 2026-06-22, endpoint devolve uma
  **lista de ~3 leituras/dia**; estrutura plana):
  ```text
  calendarDate, timestamp, timestampLocal, deviceId,
  level='MODERATE', feedbackShort='RECOVERED_AND_READY', feedbackLong='MOD_RT_LOW_SS_GOOD_ACWR_NEG',
  score=69, sleepScore=89, sleepScoreFactorPercent=88,
  recoveryTime=101, recoveryTimeFactorPercent=97,
  acwrFactorPercent=69, acuteLoad=1103,
  stressHistoryFactorPercent=73, hrvFactorPercent=93, hrvWeeklyAverage=37,
  sleepHistoryFactorPercent=65, validSleep=True, inputContext='AFTER_POST_EXERCISE_RESET'
  ```

## Arquitetura — cada camada espelha um exemplo recente do repo

O **HRV** é o análogo de ponta a ponta (adicionado recentemente): download diário →
tabela em `garmin.db` → import por `JsonFileProcessor`. O **decoupling** é o análogo de
render. O risco arquitetural é baixo; o risco real era a forma dos dados, já mitigado.

### 1. Download — `garmindb/download.py`
Espelha `__get_hrv_day` / `get_hrv`:
- `__get_training_readiness_day(directory, day, overwrite)`:
  `self.garmin.client.get_training_readiness(day.isoformat())` →
  `save_json_to_file('training_readiness_YYYY-MM-DD', data)`.
- `get_training_readiness(directory, date, days, overwrite)`: itera via `__get_stat`
  (já trata `sleep(1)` entre dias e overwrite de ontem/hoje).
- Diretório próprio via `get_training_readiness_dir()` no config manager
  (HRV reusou o de RHR; readiness recebe `TrainingReadiness/` por ser wellness distinto).

### 2. Tabela — `garmindb/garmindb/garmin_db.py`
Espelha o model `Hrv` (`table_version = 1`, `day` PK). Tabela `training_readiness` em
`garmin.db`. **Persistir todos os contribuintes** (custo zero, à prova de futuro; o
render escolhe o que exibir):

| coluna | tipo | origem JSON |
|---|---|---|
| `day` (PK) | DateTime | `calendarDate` |
| `timestamp` | DateTime | `timestamp` |
| `score` | Integer | `score` |
| `level` | String | `level` |
| `feedback_short` | String | `feedbackShort` |
| `feedback_long` | String | `feedbackLong` |
| `recovery_time` | Integer | `recoveryTime` |
| `sleep_score` | Integer | `sleepScore` |
| `sleep_score_factor_pct` | Integer | `sleepScoreFactorPercent` |
| `acwr_factor_pct` | Integer | `acwrFactorPercent` |
| `acute_load` | Integer | `acuteLoad` |
| `stress_history_factor_pct` | Integer | `stressHistoryFactorPercent` |
| `hrv_factor_pct` | Integer | `hrvFactorPercent` |
| `hrv_weekly_average` | Integer | `hrvWeeklyAverage` |
| `sleep_history_factor_pct` | Integer | `sleepHistoryFactorPercent` |

`get_stats(session, start, end)` → `{'readiness_avg', 'readiness_min', 'readiness_max'}`
(padrão de `RestingHeartRate`/`Hrv`).

### 3. Import — `garmindb/import_monitoring.py` + export em `garmindb/__init__.py`
`GarminTrainingReadinessData(JsonFileProcessor)`, regex
`training_readiness_\d{4}-\d{2}-\d{2}\.json`, espelhando `GarminHrvData`.
**Decisão de schema crítica (da sondagem):** como o JSON é uma **lista de leituras/dia**,
`_process_json` seleciona a **mais recente por `timestamp`** antes de mapear, então
`TrainingReadiness.insert_or_update(self.garmin_db, point, ignore_none=True)`.
Lista vazia ou sem `calendarDate` → retorna 0 (sem inserir).

### 4. CLI — `scripts/garmindb_cli.py` + `garmindb/statistics.py`
Espelha o wiring de `hrv`:
- `Statistics.training_readiness` (novo membro do enum em `statistics.py`).
- Entrada `Statistics.training_readiness : GarminDb` no `stats_to_db_map`.
- Flag `--training_readiness`.
- Bloco de dispatch de **download** (usa `__get_date_and_days(GarminDb(...), latest,
  TrainingReadiness, ...)` para a janela incremental) e bloco de **import**
  (`GarminTrainingReadinessData(...).process()` se `file_count() > 0`).
- Toggle em `enabled_stats` (config).

### 5. Render — `longitudinal_report.py` (builder) + `longitudinal_renderer.py`
- **Builder:** método novo (padrão `_decoupling`/`_power`) que lê a tabela e devolve
  série mensal de `score` + últimos 7 dias + cobertura; guardado no dataclass do report
  dentro de `try/except` que **nunca** quebra o relatório (loga warning e segue).
- **Renderer:** subseção na **Seção 4 (Carga de treino, periodização e segurança da
  rampa)**: sparkline + tabela meses-como-linhas (score médio) + tabela dos **últimos 7
  dias** (data, score, level, recovery_time, feedback curto) + linha de cobertura
  ("X de Y dias com leitura de prontidão"). Destaque para score, recovery_time e os
  contribuintes autonômicos (VFC/recuperação/stress); demais contribuintes ficam
  persistidos mas fora do texto por ora (YAGNI).

### 6. Testes
- Model (`test/test_garmin_db_objects.py` ou novo): cria/lê a tabela, `get_stats`.
- Importer: fixture JSON com o **caso lista-de-3** → garante seleção da última leitura;
  caso lista vazia → 0 inserções.
- Renderer: dado um report com série de readiness, a subseção aparece com score/cobertura;
  report sem dados → subseção suprimida (string vazia).
- Smoke de CLI (`--training_readiness --help` e dispatch), hermético via config de exemplo.

## Critérios de aceitação (DoD)

1. `garmindb_cli.py --training_readiness --download --import` baixa JSONs diários,
   popula `training_readiness` e é incremental (`--latest`).
2. Cada dia guarda a **leitura mais recente** (verificado com o caso lista-de-3).
3. A anamnese (`--anamnesis`) exibe a subseção de prontidão na Seção 4 com cobertura
   declarada; **suprimida** sem alarde quando não há dados (mesmo contrato do decoupling).
4. Nenhum dado fabricado; cobertura honesta ("X de Y dias").
5. `make flake8` limpo; todos os testes novos passam; `make -C test analysis` verde.
6. **Reinstalar após editar `scripts/`** (`pip install -e . --force-reinstall --no-deps`
   ou rodar da fonte) — senão `.venv/bin/garmindb_cli.py` fica obsoleto e o `--latest`/
   `--rebuild_db` usa a versão antiga (ver `docs/knowledge/2026-06-09-venv-script-staleness-rebuild-hrv-bug.md`).
7. Atualizar o changelog do roadmap north-star marcando este item e os já entregues.

## Decisões em aberto (não bloqueiam o plano)

- `recovery_time`: a unidade do `recoveryTime` (minutos vs horas) precisa ser confirmada
  no plano (a sondagem mostrou `101`; provavelmente minutos). Rotular conforme verificado.
- Reaproveitar `acute_load`/`acwr_factor_pct` para cruzar com o ACWR já calculado na
  Seção 4 (corroboração) — possível melhoria futura, fora do escopo.

## Fora de escopo (SPECs futuras)

- **Training Status** (classificação + load balance + load focus): dados aninhados
  device-keyed; dedup de VO2max/aclimatação já exibidos. SPEC própria.
- **Race predictions** (foco corrida; pouco relevante para gran fondo de ciclismo).
- Renderizar a prontidão também no relatório `--performance`.
