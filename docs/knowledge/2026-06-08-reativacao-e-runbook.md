#needs-peer-review

# Reativação do GarminDB (fork pessoal) + Runbook de Operação

**Data:** 2026-06-08
**Contexto:** Retomada do projeto após ~5 meses parado (últimos dados Jan/2026), para gerar relatórios de saúde para uma triagem médica. Documenta os bloqueadores encontrados, os consertos aplicados, e o procedimento para manter os dados atualizados.

> **Importante:** todos os consertos desta sessão foram no *ambiente* (`.venv`, `~/.GarminDb`), **não no código-fonte**. `git status` permanece limpo (nenhum `.py` rastreado alterado).

---

## 1. The Myth / Assumption (o que parecia)

- Um `git diff origin/master..HEAD` sugeria que tínhamos modificado vários arquivos *core* (`import_monitoring.py`, `garmindb_cli.py`, `requirements.txt`) e deletado testes de auth.
- Que as credenciais já estavam no config ativo e o download "só funcionaria".

## 2. The Fact / Truth (o que é verdade)

1. **Nosso fork é quase 100% aditivo.** Análise por merge-base (`b682b88`) mostra que só tocamos **3 arquivos rastreados pelo upstream**, trivialmente:
   - `garmindb/garmindb/garmin_db.py` (+1 linha: `bb_charged` em `DailySummary.get_stats`)
   - `garmindb/summarydb/summary_base.py` (coluna `bb_charged` + `view_version` 10→11)
   - `garmindb/version_info.py` (flag `prerelease`)
   - Os demais arquivos no `git diff` apareciam porque **o upstream** os mudou após a divergência. `A..B` mostra diferença líquida nos dois sentidos — não é a lista do que *nós* alteramos. Use `git log --oneline <merge-base>..HEAD` para ver só os nossos commits.
2. **Nosso código = stack de análise em 3 camadas** (`garmindb/data/` → `garmindb/analysis/` → `garmindb/presentation/`), com 4 analisadores (Sleep, Stress, Recovery, Activity/TSB) e saída em Markdown amigável para médico/LLM. Entrypoint suportado: `scripts/generate_report.py`. **Não** está integrado ao `garmindb_cli.py` (é uma ferramenta paralela que só lê os DBs).

## 3. Bloqueadores encontrados e consertos

| # | Bloqueador | Causa raiz | Conserto aplicado |
|---|-----------|-----------|-------------------|
| 1 | `import garmindb` só funcionava da raiz | Editable finder apontava para caminho morto `/Users/pmdusso/code/GarminDB/garmindb` (repo foi movido para `/code/personal/GarminDB`) | `.venv/bin/python3 -m pip install -e . --no-deps --no-build-isolation` |
| 2 | `source .venv/bin/activate` quebrado + 64 console-scripts com shebang morto | Venv não é relocável; caminho absoluto gravado no `activate` e em cada wrapper | Substituição in-place do path antigo→novo em todos os arquivos de texto do `.venv` (script Python; **não** use sed/grep — o hook `rtk` os intercepta e embaralha) |
| 3 | Download falharia: config ativo sem credenciais | `GarminConnectConfigManager` lê só `~/.GarminDb/GarminConnectConfig.json` (hardcoded); **não há merge do `.local.json`**. As credenciais estavam só no config da raiz do repo (gitignored) | Backup do config home vazio + cópia do config populado da raiz para `~/.GarminDb/` |
| — | Auth | Sessão `garth` de Dez/2025 (~5,5 meses) | Renovou sozinha (token OAuth1 dura ~1 ano) — **sem MFA** |

## 4. Anomalias de dados (resolvidas — não são bugs)

- **Tabelas `resting_hr` e `weight` vazias por design.** O RHR usado nos relatórios vem de `garmin.db / daily_summary.rhr` (populado pela importação de *monitoring*, flag `-m`), **não** da tabela `resting_hr`. Peso nunca foi registrado (sem balança inteligente — `dateWeightList` vazio nos JSON).
- **`sleep.score` é 100% NULL** neste DB → insights baseados em score de sono não disparam; o componente de sono do RecoveryAnalyzer cai no fallback neutro (70).

## 5. RUNBOOK — Atualizar os dados (incremental)

> Sempre rodar da raiz do repo, via `.venv/bin/python3`.

A "pegadinha" do `--latest`: para **atividades** ele é limitado por *contagem* (`download_latest_activities=25`), não por data. Para sono/monitoring é por *data* (cobre o gap inteiro). Por isso o procedimento abaixo é em estágios:

```bash
cd /Users/pmdusso/code/personal/GarminDB

# 1) Atividades recentes (rápido, valida auth)
.venv/bin/python3 scripts/garmindb_cli.py -a -d -i --analyze -l

# 2) Backfill completo de atividades, se o gap > 25 atividades (baixa só os faltantes, até 1000)
.venv/bin/python3 scripts/garmindb_cli.py -a -d -i --analyze

# 3) Monitoring + sono incremental (por data, cobre o gap inteiro)
.venv/bin/python3 scripts/garmindb_cli.py -m -s -d -i --analyze -l
```

**Pular `-r` (rhr) e `-w` (weight):** redundantes/vazios e caem no fallback de start_date (backfill inútil). O RHR já vem via `-m`.

**Verificação pós-update:**
```bash
sqlite3 ~/HealthData/DBs/garmin.db "SELECT MAX(day) FROM daily_summary; SELECT MAX(day) FROM sleep;"
sqlite3 ~/HealthData/DBs/garmin_activities.db "SELECT MAX(start_time) FROM activities;"
sqlite3 ~/HealthData/DBs/garmin.db "PRAGMA integrity_check;"
```

**Erros benignos no log (ignorar):** `device_info ... tacx ... 'NoneType' tzinfo` (rolo TACX com timestamp nulo — o summary importa normalmente); 2 FIT antigos truncados de 2023.

## 6. RUNBOOK — Gerar relatório

```bash
# Janela explícita (recomendado — datas determinísticas)
.venv/bin/python3 scripts/generate_report.py --start 2026-05-09 --end 2026-06-07 \
  -o docs/relatorio-saude-30dias.md

# Ou relativo a hoje (só funciona com dados atualizados): --period daily|weekly|monthly
```

## 7. Sync com o upstream — ✅ CONCLUÍDO em 2026-06-08

**Resultado:** `master` agora está **0 commits atrás** de `origin/master` (26 à frente). Merge feito fast-forward; DBs reconstruídos no schema novo; relatórios validados (51 testes de análise passando).

**O que a recon errou (validar > confiar):** o `origin/master` **também** traz a migração de auth `garth` → `python-garminconnect` (commit `114f6ee`), não só o `develop`. Confirmado pelo `requirements.txt` e por `download.py` (que agora importa `garminconnect`). **Consequência prática:** o próximo `--download` pedirá re-login via `garminconnect` (novo token store `~/.GarminDb/garmin_tokens.json`, possível MFA). Não afeta relatórios (leem DBs).

**Regressão encontrada e corrigida (commit `06c8ab4`):** o Date→Datetime do upstream fez as colunas `day` retornarem `datetime`, quebrando o `RecoveryAnalyzer` (`TypeError: can't compare datetime.datetime to datetime.date` em `recovery_analyzer.py:89` e `:317`). Fix no boundary do repositório (`garmindb/data/repositories/sqlite.py`): helper `_to_date()` que normaliza `row.day` → `date` ao construir `SleepRecord`/`DailySummaryRecord` (backward-compatible — `datetime` é subclasse de `date`, então checa `datetime` primeiro).

**Rollback se necessário:** backup dos DBs pré-sync (schema antigo) em `~/HealthData/DBs_backup_pre-sync_20260608/`. Para voltar ao estado anterior: `git reset --hard ecdb32f` + restaurar os DBs do backup.

### Como foi feito (referência)

Análise por `git merge-tree` (simulação read-only): merge de `origin/master` gera **1 conflito** (`summary_base.py`); `origin/develop` gera **2** (`summary_base.py` + `version_info.py`). O custo real **não** são conflitos git, mas:
- **Rebuild obrigatório do DB** (upstream sobe versões de schema: Date→Datetime, nova tabela `hrv`, etc.). Como os dados já exigiram re-download, o rebuild "pega carona".
- **`develop` tem migração de auth quebrante** (`garth` → `python-garminconnect`, commit `114f6ee`) que invalida a sessão garth e força re-auth pelo novo adapter.

**Estratégia recomendada:** sincronizar com `origin/master` primeiro (conservador: mantém `garth`, traz o fix Date→Datetime, 1 conflito), validar, e só depois avaliar `develop` para ganhar **HRV** (RMSSD — valioso para triagem médica).

```bash
git fetch origin
git switch -c sync/upstream-master master
git merge origin/master            # conflito esperado: summary_base.py
# Resolver mantendo AMBOS: view_version=11 (nosso, bb_charged) E _table_version=6 (upstream)
.venv/bin/pip install --upgrade -r requirements.txt
make flake8 && make -C test all
.venv/bin/python3 scripts/garmindb_cli.py --rebuild_db   # obrigatório após bump de schema
```

---

*Documento gerado durante a sessão de reativação. Revisar e, se aprovado, mover o conteúdo perene para o README/CLAUDE.md do projeto.*
