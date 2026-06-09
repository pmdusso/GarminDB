# Spec — Relatório de Performance (rumo ao L'Étape top-100)

**Data:** 2026-06-08
**Status:** Rascunho — aguardando revisão
**Autor:** Pedro + Claude

---

## Contexto e propósito

Pedro é ciclista amador de endurance mirando **top-100 no L'Étape Campos do Jordão 2026** (Percurso Longo, 107 km) — ou seja, **sub-3h17**, ante 3h56 / 493º em 2024. 2026 é um ano pessoalmente exigente; por isso o relatório é, além de bússola de performance, um **espelho honesto e sem drama de forma física E recuperação** — a recuperação/prontidão entra como **salvaguarda de bem-estar**, não só como insumo de treino.

O fork do GarminDB já tem uma stack de análise em 3 camadas (`data → analysis → presentation`) que gera relatórios de saúde em Markdown. Este spec **adiciona um relatório orientado a performance** por cima, **reusando** essa stack e acrescentando análise de potência.

## Objetivos

- Um relatório **Markdown** que funciona como **snapshot autossuficiente** e, regenerado ao longo do tempo, mostra **tendência e deltas**.
- **Espinha:** W/kg, FTP, VO2max, peso, carga de treino (CTL/ATL/TSB). **Suporte:** sono, RHR, estresse, recuperação.
- Cada métrica enquadrada como **"você está aqui → meta (gap, Δ desde o último)"**.
- **1 insight acionável por área**, uma **luz de prontidão (🟢🟡🔴)** e um **foco recomendado** para o próximo bloco.

## Fora de escopo (esta iteração)

- **PDF** (upgrade futuro).
- **Dashboard HTML/interativo** (descartado — ficamos no documento Markdown).
- **Importar potência nativamente no banco** (upgrade futuro "C"). Nesta versão, a potência é **lida dos JSONs brutos em tempo de relatório**, sem mexer na ingestão nem no schema.

## Estrutura do relatório

| Seção | Conteúdo | Insight |
|---|---|---|
| **Resumo Executivo** (topo) | Scorecard da espinha (atual·meta·gap·Δ) + **luz de prontidão** + **top 3 prioridades** | — |
| **§1 Motor** | FTP, **W/kg**, curva de potência (5s/1/5/20/60min), VO2max, distribuição de intensidade por zona | 1 |
| **§2 Carga de Treino (TSB)** | CTL/ATL/TSB, monotonia/strain, ACWR, volume semanal | 1 |
| **§3 Recuperação & Prontidão** | recovery score, RHR vs baseline, sono, estresse → **luz 🟢🟡🔴** | 1 |
| **§4 Peso & W/kg** | tendência de peso + quanto cada kg move o W/kg rumo ao alvo | 1 |
| **§5 O que mudou** | deltas vs último relatório *(só a partir do 2º)* | — |
| **§6 Foco do próximo bloco** | 1-3 prioridades acionáveis derivadas do acima | — |

O dispositivo unificador é **"você está aqui → meta"** em toda métrica. A coluna **Δ** é o que liga snapshot (3) a recorrente (1): vazia/"baseline" no 1º relatório; conta a história do progresso do 2º em diante.

**Regras de apresentação (para remover ambiguidade):**
- **Luz de prontidão** deriva do `RecoveryAnalyzer.daily_readiness()` já existente (score 0-100 + intensidade recomendada): 🔴 = rest/light, 🟡 = moderate, 🟢 = intense.
- **Setas Δ**: ↑ melhora rumo à meta, ↓ piora, → estável (limiar de "estável" por métrica, ex. ±2% W/kg).
- Cada **insight** carrega severidade herdada dos analisadores (INFO/POSITIVE/WARNING/ALERT) e mapeia para emoji (ℹ️/✅/⚠️/🚨).

## Métricas, fontes e metas

| Métrica | Fonte | Exemplo atual | Meta | Cálculo |
|---|---|---|---|---|
| **FTP** | `performance_targets.json` (valor configurado) | 325 W | manter / ↑335 | **Valor declarado** (autoritativo, do Wahoo/TP). Cross-check = melhor 20min × 0,95 dos JSONs |
| **W/kg** | FTP ÷ peso atual | 3,81 | 4,0–4,2 | FTP / média de peso recente |
| **Peso** | tabela `weight` | 85,2 kg | ~81 kg | média das pesagens recentes |
| **VO2max** | `cycle_activities.vo2_max` | 56 | manter↑ | máx/média recente |
| **CTL/ATL/TSB** | `ActivityAnalyzer` (training_load) | CTL 76, TSB +13 | construir CTL | modelo já implementado |
| Sono/RHR/estresse | DB (sleep, daily_summary) | ~7,7h; RHR vs baseline | — | analisadores existentes |

**Reconciliação FTP declarada vs. observada:** a FTP configurada (325 W) hoje é **maior que qualquer esforço de 20min registrado nos dados** (319 W em 2023, 281 W em 2026). O relatório **sinaliza essa divergência** e sugere um **teste de FTP** quando os dados não corroboram o valor declarado. Esse é um recurso, não um bug.

**Metas de W/kg para top-100:** ~4,0 (entrada no páreo) a 4,2 (margem). Ex.: 325 W @ 81 kg = 4,0; @ 80 kg = 4,06; @ 77 kg = 4,2. Com FTP já sólido, **peso é a alavanca primária**.

## Arquitetura

### Componentes novos
- **`PowerAnalyzer`** — `garmindb/analysis/power_analyzer.py`. Lê `~/HealthData/FitFiles/Activities/activity_*.json`; extrai `normPower`, `avgPower`, `maxAvgPower_{1,5,10,20,30,60,120,300,600,1200,1800,3600}`, `activityType`. Calcula: **curva de potência** (melhor potência média por duração, janela "atual" 90d + PB de sempre), **W/kg**, **distribuição de intensidade por zona** (zonas derivadas da FTP), **cross-check de FTP**.
- **`performance_targets.json`** (config novo, em `~/.GarminDb/`) — `{ ftp_watts, weight_target_kg, wkg_target, race_name, race_date }`. Fonte das colunas "meta/gap".
- **Estado de deltas** — `~/HealthData/reports/last_metrics.json`. Snapshot das métricas-chave do último relatório; usado para Δ e §5; atualizado a cada execução.
- **`PerformancePresenter`** — em `garmindb/presentation/markdown/`. Reusa padrões do `MarkdownPresenter`; renderiza scorecard + 6 seções.
- **`PerformanceReport`** (modelo) — agrega espinha + suporte + deltas + metas.
- **Entry point** — `scripts/generate_report.py --performance` (ou `scripts/performance_report.py`). Aceita `--start/--end` (janela do snapshot; default últimos 30 dias).

### Fluxo de dados
```
DB (sono/RHR/estresse/CTL/peso/VO2max)   ─┐
JSONs de atividade (potência)            ─┼─> analisadores ─> PerformanceReport ─> Markdown
performance_targets.json (FTP/metas)     ─┤   (Sleep/Stress/Recovery/Activity + PowerAnalyzer novo)
last_metrics.json (deltas)               ─┘
```

### Reuso
- `SleepAnalyzer`, `StressAnalyzer`, `RecoveryAnalyzer`, `ActivityAnalyzer` (CTL/ATL/TSB) → suporte + carga.
- `SQLiteHealthRepository` → métricas de DB, peso, VO2max.
- `PowerAnalyzer` (novo) → espinha de potência.

## Tratamento de erros / casos de borda
- **Ride sem potência** → fora da curva; reporta cobertura (% de rides com potência).
- **Sem peso** → W/kg indisponível; mostra só FTP + sugere pesar.
- **Sem relatório anterior** → coluna Δ vazia, rótulo "baseline"; §5 omitida.
- **FTP declarada > melhor 20min observado** → flag "considere um teste de FTP".
- **Dir de JSONs ausente / JSON ilegível** → pula, registra cobertura (sem quebrar o relatório).

## Testes
- **Unit `PowerAnalyzer`**: curva de potência a partir de JSONs-amostra; cálculo de W/kg; cross-check de FTP; distribuição de zonas; bordas (sem potência, sem peso).
- **Unit deltas**: 1ª execução (baseline) vs subsequentes.
- **Smoke**: gerar relatório completo nos DBs reais; assertar todas as seções presentes + scorecard preenchido.

## Decisões (defaults adotados — vetar se discordar)
1. **Local do config:** `~/.GarminDb/performance_targets.json` (junto do config principal).
2. **Janela da curva de potência:** mostrar **ambos** — melhor de 90d ("atual") + PB de sempre.
3. **Meta de W/kg:** 4,0 (entrada) com 4,2 como stretch.
4. **Entry point:** flag `--performance` no `generate_report.py` existente (reuso de wiring), não um script novo.
5. **Janela default do snapshot:** últimos 30 dias (override por `--start/--end`).
