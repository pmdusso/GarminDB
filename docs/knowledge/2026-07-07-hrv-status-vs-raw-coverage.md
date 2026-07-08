#needs-peer-review

# HRV: "HRV Status" (garmin.hrv) começa em 2024, mas a HRV bruta existe desde a troca de relógio (out/2022)

**Data:** 2026-07-07

## Contexto

Ao mapear intervalos de datas do banco, notou-se que `garmin.hrv` começa em
**2024-02-16**, embora o usuário tenha trocado de relógio em **out/2022** e
esperasse HRV desde então.

## A suposição (Mito)

"Falta HRV de out/2022 a fev/2024" — presumindo um gap de download ou de import,
ou que o `hrv_start_date` cortou o histórico.

## O fato (Verdade)

Existem **duas fontes distintas de HRV** no banco, com coberturas diferentes:

1. **`garmin.hrv`** (baixada como JSON de `HealthData/RHR/hrv_*.json`) = o **HRV
   Status calculado pela Garmin** (baseline + classificação LOW/BALANCED/HIGH).
   Só tem dado **a partir de 2024-02-16**. A própria API da Garmin retorna `{}`
   (vazio) para todas as datas anteriores — não é corte nosso.

2. **`monitoring_hrv_value`** (leituras brutas) e **`monitoring_hrv_status`**
   (status noturno dos FITs) = as leituras noturnas reais de HRV. Existem
   **desde 2022-10-04**, exatamente a data da troca de relógio.

O relógio SEMPRE gravou HRV bruta desde out/2022. O que a Garmin só passou a
computar em fev/2024 foi o **produto derivado "HRV Status"** (precisa de ~3
semanas de uso noturno consistente para formar baseline; recurso liberado por
firmware/conta ao longo de 2022–2023).

## Evidência

- Contagem de leituras brutas por ano em `monitoring_hrv_value`:
  2022=7.647, 2023=24.866, 2024=29.341, 2025=31.198, 2026=16.728.
- `monitoring_hrv_status` de out/2022: `last_night_average` preenchido (75, 80,
  70…) mas `baseline_low/high` VAZIOS e `status = 0` ("sem status"). O relógio
  mediu a HRV; a Garmin não tinha baseline ainda.
- JSONs baixados de 2023-12-31 a início de fev/2024 = `{}` (vazios). Primeiro
  não-vazio: `hrv_2024-02-17.json` (com `hrvSummary.status = "LOW"`, baseline etc).
- Config `hrv_start_date = 12/31/2023`: nunca pedimos Status JSON antes de
  dez/2023 — mas as evidências acima indicam que não há Status lá de qualquer forma.

## Implicação analítica

- **Para HRV histórica (2022–2024), ler `monitoring_hrv_value` /
  `monitoring_hrv_status.last_night_average`, NÃO `garmin.hrv`.**
- `garmin.hrv` só serve para o HRV Status (baseline/classificação) de fev/2024 em diante.
- Baixar o Status JSON de out/2022–dez/2023 (baixando `hrv_start_date`) provavelmente
  volta vazio — não vale o esforço.
- Padrão geral: métricas *derivadas* da Garmin (HRV Status, Training Status, etc.)
  podem começar bem depois do dado bruto que as alimenta. Sempre distinguir
  "leitura do sensor" de "produto calculado" ao mapear cobertura temporal.
- O catálogo (`docs/catalogo-dados-garmindb.md`) foi atualizado com essa distinção.
