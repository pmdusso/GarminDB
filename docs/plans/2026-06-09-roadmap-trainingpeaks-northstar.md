#needs-peer-review

# Roadmap: TrainingPeaks como north-star — extrair o máximo do Garmin

**Data:** 2026-06-09 · **rev. consolidada** (ai-review multi-modelo + auditoria de cobertura + 2 checks de dados)
**Status:** Rascunho / roadmap — **nada implementado ainda**.
**Fontes desta revisão:**
- ai-review multi-modelo (gemini-3.1-pro, gpt-5.5, opus-4.7, qwen3-coder) sobre a v1 deste doc.
- Auditoria de cobertura do GarminDB → `docs/plans/2026-06-09-garmindb-data-coverage-audit.md`.
- 2 checks de dados (estrutura dos JSONs de atividade + cobertura real de potência).

**Contexto:** O relatório de anamnese (`docs/reports/relatorio-anamnese-2025-2026.md`) cobre fisiologia e carga, mas sua maior lacuna honesta era **potência**. O dashboard do TrainingPeaks é **referência visual** (quais gráficos ter) — **não** fonte de dados (sem API). Todos os números saem do Garmin/GarminDB. O fork está **atual** (`v3.8.0 == upstream`); as lacunas são do GarminDB, não defasagem do fork.

---

## Conclusão central (revisada)

O maior ganho **não é potência** — é **dado que já guardamos e nunca consultamos**. O ai-review (que pedia uma Fase 0 mais clínica) e a auditoria (que achou colunas grandes e populadas sem uso) **convergiram**: a Fase 0 deve **colher métricas clínicas já capturadas** (SpO2, respiração, Anaerobic TE, banda completa de HRV, Body Battery charge) — **zero import, zero risco de fabricação, alto valor médico**. A potência ficou **de-riscada** (curva + zonas já prontas para ~589/750 pedais; cobertura recente forte), mas é **Fase 1**, não 0.

---

## Achados dos checks (correções importantes vs. a v1)

### Onde a potência realmente mora
- A **curva mean-max** (`maxAvgPower_5/60/300/1200/3600`) e as **zonas** (`powerTimeInZone_1..7`) vêm **pré-computadas pelo Garmin** nos arquivos **summary** `activity_<id>.json`:
  - **589** pedais com `maxAvgPower_1200` (curva → FTP-por-20min)
  - **750** pedais com `powerTimeInZone_*` (zonas)
- Os `activity_details_*.json` têm **só** `summaryDTO.{average,normalized,max}Power` (788) — **sem** curva, **sem** série por-segundo (`metricDescriptors = 0`).
- ⚠️ Correção da v1: **NÃO** trocar o `PowerAnalyzer` para ler `summaryDTO` dos *details* — os details são *mais pobres*. O `PowerAnalyzer` **já lê as chaves certas** dos *summary*; o "37 pedais" foi **artefato da janela de 30 dias** do relatório de performance, não um limite real.
- Watts **por-segundo**: só no `.fit` bruto — o submódulo `Fit` parseia o campo de potência (field 7), mas o `ActivityFitFileProcessor` **descarta**. (Recuperável; ver Fase 2.)

### Cobertura de potência (forte e recente)
- **2025:** 216 pedais com potência (188 ≥60min). **2026:** 96 (74 ≥60min). Quase todos **outdoor longos**.
- Indoor/virtual (viés de trainer): 17 em 2025, 1 em 2026 — minoria, a rotular/separar.
- → o "FTP/W·kg atual" é **bem sustentado** por dados reais (corrige o pessimismo dos revisores).

---

## Inventário de oportunidades (da auditoria)

### A) Já no banco, sem uso — **ganhos rápidos, zero import, zero risco**
| Dado | Fonte | Cobertura | Valor clínico |
|---|---|---|---|
| **SpO2** | `monitoring_pulse_ox` (544.818 linhas), `daily_summary.spo2_avg` (51,6%), `sleep.avg_spo2` (50,2%) | boa | **Alto** — aclimatação a altitude (prova de montanha) |
| **Respiração** | `monitoring_rr` (1.460.069), `daily_summary.rr_waking_avg` (55,3%), `sleep.avg_rr` (51,4%) | boa | Médio-Alto — estresse/recuperação/respiratório |
| **Anaerobic Training Effect** | `activities.anaerobic_training_effect` (85,5%) | alta | Médio — ao lado do aeróbico que já usamos; trivial |
| **Banda completa de HRV** | `monitoring_hrv_status.{weekly_average, baseline_low/high, status}` | alta | **Alto** — hoje só lemos `last_night_average` |
| **Body Battery charge** | `daily_summary.bb_charged` | alta | Médio — recarga noturna (recuperação) |
| **Sono detalhado** | `sleep.{light_sleep, awake, avg_stress}`, `sleep_events` (7.529) | boa | Médio |
| **Laps** | `activity_laps` (14.557) | alta | Baixo-Médio — intervalados/splits |

### B) Lacunas mais fundas
- **Potência:** em nenhuma tabela — `activity_records` (4,73M linhas) não tem coluna `power`; watts só no `.fit` (field 7 descartado) e nos summary/details JSON. Recuperável dos nossos próprios arquivos (Fase 1/2).
- **Tabela `hrv` vazia** (0 linhas) apesar do GarminDB suportar → conserto de **import** (passe `--hrv`).
- **Training Status / Readiness / Recovery Time / Lactate Threshold:** **não suportados** pelo GarminDB (sem endpoint/importer/tabela) — alto valor médico, alto esforço.
- **% Gordura:** confirmado **não suportado** (só `weight`).

---

## Plano faseado (re-priorizado)

### Fase 0 — Colher os clínicos já capturados  ·  ALTO valor / ZERO import
1. **SpO2:** tendência mensal (`daily_summary.spo2_avg` + `sleep.avg_spo2`) com nota de relevância p/ altitude.
2. **Respiração:** `rr_waking_avg` + `sleep.avg_rr` (tendência).
3. **Anaerobic Training Effect:** série mensal ao lado do aeróbico.
4. **Banda de HRV completa:** `baseline_low/high`, `status`, `weekly_average` — enriquece a Seção 2 (cardiovascular/autonômico).
5. **Body Battery charge** (`bb_charged`) + **sono detalhado** (light/awake/avg_stress).
6. **(clínico, do ai-review)** FC máxima **operacional** (p99 ou mean-max 5s, por esporte — **não** `max` cru, que vai a 230 por spike); reaproveitar monotonia/strain que já temos.
- **DoD:** cada métrica com **cobertura declarada** ("X de Y dias"); 1 teste por métrica; nenhuma fabricação; só entra no relatório o que tem dado real.

### Fase 1 — Potência (de-riscada, via *summary files*)  ·  ALTO valor / esforço médio
- Rodar o `PowerAnalyzer` **longitudinalmente** (não em 30d): **curva** (589) + **zonas** (750) + *merge* de `avg/NP` dos *details* (788) por `activity_id`.
- **eFTP** = melhor `maxAvgPower_1200` × 0,95, com **gate de publicação**: só publica FTP "medido" se houver esforço duro real na janela (limiar de IF/contagem mínima); senão volta para **"configurado, sem teste recente"**. Rotular **"estimado, não testado em laboratório"**; sanity vs. melhor `NP` de ~1h.
- **Qualidade (do ai-review):** **não** usar `maxPower` cru (usar `maxAvgPower_5`); `NP` só para `moving_time ≥ 30min`; **rotular/separar indoor/virtual**; **W·kg com peso pareado por pedal (±7d)**, dropando se exceder.
- **Cobertura declarada** ("X de Y pedais com potência") + **reprodutibilidade** (`as_of`, janela "alltime" com data de corte).
- **DoD:** curva validada por *golden file*; `NP` recalculado < 2% do `summaryDTO.normalizedPower`; testes de fallback/merge/peso-pareado; bloco de FTP **suprimido** com aviso quando o gate não passa.

### Fase 2 — Profundidade (per-second, import, novos imports)  ·  alto esforço
- **Decoupling cardíaco** (Pa:Hr / Hr:speed) em longos — dos streams `activity_records` (hr+speed) + `.fit` (power). Alto valor clínico (o ai-review destacou).
- **Importar potência pro DB**: `.fit` campo 7 → nova coluna/tabela (`activity_records.power` ou `power_records`): bump de `table_version` + migração + backfill seletivo + testes (pedal **sem** medidor importa `NULL` em silêncio). **SPEC própria.**
- **Conserto da tabela `hrv`** (passe `--hrv` no import).
- **Investigar Training Status / Readiness / Recovery / Lactate** (não suportados upstream — antes, checar issues do `tcgoetz/GarminDB`).

---

## Perguntas RESOLVIDAS (eram "abertas" na v1)
- ✅ A curva mora nos *summary* (589); *details* só resumo → **não** migrar para details.
- ✅ Cobertura recente é forte (96 em 2026 / 216 em 2025, outdoor longos).
- ✅ Série por-segundo de watts só no `.fit` (field 7 descartado pelo processor).
- ✅ Fork atual (`v3.8.0`); lacunas são do GarminDB, não do fork.

## Decisões ainda em aberto
- Regime exato do **gate de eFTP** (janela; limiar de esforço/IF mínimo; contagem mínima de candidatos).
- Indoor/outdoor: **rotular** cada PB ou **curvas separadas**?
- % Gordura: importar de fonte externa (Garmin Index)? — **fora de escopo** por ora.
- Quando virar SPEC executável, mover para `docs/superpowers/specs/` (padrão já existente).

## Princípios (não-negociáveis)
- Tudo lido de banco/arquivos reais; **nada fabricado** (vai a um médico).
- Potência/qualquer métrica com **cobertura honesta** declarada.
- Reusar a stack `data → analysis → presentation`; **testes** para cada peça.
- **Atualizar este doc** conforme as fases avançam (não criar versões novas) + manter o changelog abaixo.

## Changelog
- **2026-06-09 v1:** criação (mapa de viabilidade + plano faseado inicial).
- **2026-06-09 rev:** consolidado ai-review + auditoria de cobertura + 2 checks. Corrigida a localização da potência (curva/zonas nos *summary*, não nos *details*; "37" era artefato de janela). Re-priorizada a Fase 0 para **colher clínicos já capturados** (SpO2/respiração/Anaerobic TE/banda HRV/BB charge). Adicionados regime de eFTP, requisitos de qualidade, DoD/testes por fase, e a trilha de decoupling/import na Fase 2.
