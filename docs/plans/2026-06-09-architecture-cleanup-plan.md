# Plano: Limpeza & Modernização de Arquitetura (v2.0 prep)

**Data:** 2026-06-09 · **Revisado:** 2026-06-10 (após ai-review multi-LLM +
verificação contra o código) · **Modo:** cleanup seguro (sem refactor de camadas)
**Branch sugerida:** `chore/architecture-cleanup` **a partir de `develop`**
(o `AGENTS.md` manda abrir PR contra `develop`, não `master`; adicionar-se a
`contributors.txt`).

> **Mudanças desta revisão:** ordem reordenada para **A → C → B → D → E** (a rede
> de segurança de testes entra antes da mudança estrutural). Workstream C
> reescrito após descobrir **3 bloqueadores reais**. Workstream B teve a lista de
> edição do Makefile completada. Critérios de aceitação refeitos (eram
> inverificáveis). §7 corrigido (a premissa de "dead code" estava errada).

## Escopo (decisões confirmadas)
1. Notebooks → arquivar todos em `docs/notebooks/` (arquivo morto).
2. Camadas → **só cleanup seguro agora**. Refactor de acesso a dados (repository
   vs sqlite3 direto) e dedup de markdown ficam para **fase separada** (ver §7).
3. Testes órfãos → integrar ao Makefile **e** ao CI (`verify_commit`) — mas só o
   subconjunto comprovadamente hermético (ver Workstream C).

## Pré-flight (verificado contra o código — com correções)
- **OK:** Nenhuma credencial **rastreada** (só `garmindb/GarminConnectConfig.json.example`).
  `*.log`, configs reais e `garth_session` estão no `.gitignore`.
  ⚠️ Correção: **`temp_config/` NÃO está ignorado como diretório** — só dois paths
  específicos (`temp_config/GarminConnectConfig.json`, `temp_config/garth_session`).
- **OK:** pytest 9.0.2 instalado no venv, **não declarado** em nenhum requirements.
- **OK:** A suíte é **mista** (unittest + pytest `tmp_path`/`assert`) → pytest é o
  único runner que roda os dois estilos.
- 🔴 **NOVO (bloqueador de empacotamento):** `setup.py:41` lista `packages=`
  manualmente — `[garmindb, garmindb.garmindb, garmindb.fitbitdb,
  garmindb.mshealthdb, garmindb.summarydb]` — **sem `garmindb.analysis`,
  `garmindb.data`, `garmindb.presentation`**. O CI instala via **wheel** (não
  editable: `install_all → install: dist/*.whl`). Localmente funciona porque o
  venv é editable; **no CI a suíte de análise não importaria**. Tem de ser
  corrigido antes de C (ver C, passo 0).
- 🔴 **NOVO (bloqueador de coleta):** existem **dois `models.py`**
  (`garmindb/analysis/models.py` e `garmindb/data/models.py`); `test_data_models.py`
  e `test_markdown_presenter.py` fazem `from models import ...` via `sys.path` hack.
  Rodar os ~28 num **único processo pytest** falha na coleta
  (`ImportError: cannot import name 'SleepRecord'`). Confirmado empiricamente.

---

## Workstream A — Remover/arquivar cruft da raiz
Scripts ad-hoc órfãos (confirmado: **sem** imports/refs em test/, Makefile,
scripts/, docs/, garmindb/, setup.py, MANIFEST.in, .github/ — só aparecem no
próprio plano):
- `debug_insert.py` · `recompute_q4_report.py` · `test_activity_report.py`
- `test_recovery_report.py` · `test_stress_report.py`

⚠️ **Nuance (consenso do review):** os 5 **importam APIs vivas** do pacote
(`garmindb.data.repositories`, `garmindb.analysis.*`, `garmindb.presentation.*`);
`debug_insert.py` escreve num DB real. "Sem refs" ≠ "sem uso" — podem ser
ferramentas de debug manuais do mantenedor. **Decisão (default seguro):** mover
para `scripts/legacy/` com um `README.md` ("scripts ad-hoc legados, não mantidos")
em vez de `git rm`. Só `git rm` se o mantenedor confirmar que não usa nenhum.
**Manter:** `setup.py`, `Makefile`, `defines.mk`, `MANIFEST.in`.

## Workstream C — Integrar testes ao Makefile + CI (via pytest)
**Reordenado para antes de B** (a suíte vira rede de segurança da mudança
estrutural). **3 bloqueadores a resolver primeiro:**

**Passo 0 — corrigir empacotamento (bloqueador):** em `setup.py`, trocar a lista
manual de `packages=` por `find_packages()` (ou adicionar `garmindb.analysis`,
`garmindb.data`, `garmindb.presentation`). Sem isso a wheel do CI não contém esses
subpacotes e a suíte de análise falha no import. Validar com
`pip install dist/*.whl` em venv limpo + `python -c "import garmindb.analysis,
garmindb.data, garmindb.presentation"`.

**Passo 0b — resolver a colisão dos `models.py` (bloqueador):** NÃO rodar os 28
num único `pytest`. Opção recomendada (menor risco): alvo `analysis` roda
**por-arquivo** num loop (espelha o padrão `test_%` existente). Alternativas:
`[tool.pytest.ini_options] importmode=importlib` + `conftest.py`/`test/__init__.py`,
ou qualificar os imports em `test_data_models.py`/`test_markdown_presenter.py`
(`from garmindb.analysis.models import ...` / `from garmindb.data.models import`).

**Passo 1 — declarar pytest:** adicionar **`pytest==9.0.2`** (pinado) a
`dev-requirements.in`. Regenerar `dev-requirements.txt` **num venv limpo**
(`make clean_venv setup`) ou via `pip-compile` — **não** com `make
dev-requirements.txt` no venv atual, pois `pip freeze -r` arrasta Jupyter, o
editable `-e git+ssh://…` e deps pessoais para o CI. Revisar o diff.

**Passo 2 — classificar os 28 testes (`safe` vs `manual`):** rodar **cada um** num
ambiente CI-like limpo (sem `~/HealthData/`, sem `~/.GarminDb/`) e separar:
- **Comprovadamente seguros (verificado):** `test_download_auth_adapter`,
  `test_garmin_connect_auth_adapter` são **totalmente mockados** (`FakeAdapter`/
  `FakeGarmin`) — passam isolados, sem rede. (O plano antigo errou o alvo do
  risco aqui.) Também seguros: analyzers/presenters puros, `test_report_state`,
  `test_markdown_presenter`, os `test_*_phase1`, `test_power_import_phase2_sp1`.
- **`manual` (fora do `verify_commit`):** `test_integration` **exige**
  `~/.GarminDb/GarminConnectConfig.json` + DBs reais (`setUpClass` →
  `sys.exit(-1)` em runner limpo). Verificar também `test_sleep_analyzer`,
  `test_health_analyzer`, `test_recovery_analyzer`, `test_sqlite_repository`,
  `test_db_metrics`, `test_repositories`, `test_weight_series` (instanciam
  `GarminConnectConfigManager`/`SQLiteHealthRepository` ou exigem dados).
- Começar o alvo `analysis` **só** com o subconjunto hermético; os demais vão para
  um grupo `manual`. Padronizar `@pytest.mark.skipif(not <config/DB>)` no estilo
  que `test_performance_cli_smoke.py` já usa.

**Passo 3 — `test/Makefile`:** novo alvo `analysis` que roda **por-arquivo** a
lista curada `safe` (não num pytest único). Esboço:
```make
ANALYSIS_PYTEST=test_activity_analyzer test_recovery_analyzer ... (só os SAFE)
analysis:
    @for t in $(ANALYSIS_PYTEST); do $(PYTHON_PATH) -m pytest -p no:cacheprovider test/$$t.py || exit 1; done
```

**Passo 4 — wiring:** adicionar `analysis` a `all` e a `verify_commit` (hoje
`verify_commit: module_versions db_objects` — não roda pytest nenhum).

**Passo 5 — ampliar `make flake8`:** o alvo atual linta só `garmindb/*.py`,
`garmindb/garmindb`, `summarydb`, `fitbitdb`, `mshealthdb` — **não** cobre
`garmindb/analysis`, `garmindb/data`, `garmindb/presentation`, `scripts`. Incluí-
los (senão "flake8 limpo" não linta o código novo).

**Passo 6 — CI (`.github/workflows/pythonapp.yml`):** `verify_commit` já roda no
passo Test e `devdeps` instala `dev-requirements.txt`; após os passos acima, a
suíte `safe` entra no CI. Validar num runner limpo (não na máquina do mantenedor).

## Workstream B — Arquivar notebooks (**editar antes de mover**)
Mover `Jupyter/` (15 `.ipynb` + `graphs.py`, `jupyter_funcs.py`, `maps.py`,
`__init__.py`, `requirements*.{in,txt}` = 23 arquivos) → `docs/notebooks/`.

**Passos (ordem importa — editar refs ANTES do `git mv`):**
1. **Editar todas as refs `Jupyter/` no Makefile** (rodar `grep -n "Jupyter" Makefile`
   e tratar TODAS — o plano antigo só listava 5 alvos e esquecia duas):
   - alvos `Jupyter/requirements.txt`, `Jupyter/requirements_graphs.txt`,
     `graphdeps`, `jupiterdeps`, `alldeps` → remover (a cadeia
     `graphdeps→jupiterdeps→alldeps` é folha órfã; nada default/CI a invoca — o
     "risco de cross-deps" estava **superestimado**).
   - **`remove_deps`** (≈ l.188-189): `pip uninstall -y -r Jupyter/requirements.txt`
     e `…requirements_graphs.txt` — quebraria `make remove_deps`/`clean_deps`.
   - **`clean`** (≈ l.205,211): `rm -f Jupyter/*.log`, `Jupyter/*stats.txt` —
     no-op silencioso, mas ref morta (`clean` é dep de `realclean`/`publish`).
2. **Editar docs com refs vivas** (além do Workstream E): `README.md` (seção
   "Jupyter Notebooks"), `AGENTS.md:8`, e **`garmindb/GarminDB_Comprehensive_Documentation.md`**
   (descreve `Jupyter/` + lista notebooks — não estava no escopo antigo).
3. `.gitignore:108`: `Jupyter/.ipynb_checkpoints/` → `docs/notebooks/.ipynb_checkpoints/`.
4. **`git mv Jupyter docs/notebooks`** (alvo não pré-existe → rename limpo).
5. **Remover** `docs/notebooks/__init__.py` (não mover) — senão fica um package
   fantasma `docs.notebooks` importável que confunde flake8/IDEs.
6. Limpar o `Jupyter/.ipynb_checkpoints/` solto no disco (untracked; `git mv` só
   move rastreados, deixando a pasta velha para trás).
7. `docs/notebooks/README.md` curto marcando arquivo morto.

## Workstream D — `.gitignore` & raiz
- `.gitignore` cobre `*.log`, configs reais, `temp/`. Ajustar a linha do Jupyter
  (Workstream B, passo 3). **Opcional:** ignorar `temp_config/` como diretório
  inteiro (hoje só 2 arquivos são ignorados).
- Remover do disco logs soltos da raiz (não rastreados) é cosmético.

## Workstream E — Documentação
- `CLAUDE.md` e `AGENTS.md`: comando de teste passa a incluir `analysis`
  (`make -C test all` + `make -C test analysis`); pytest como dep de dev;
  notebooks arquivados em `docs/notebooks/`. Atualizar também o bullet
  `AGENTS.md:8` ("Notebooks and assets: Jupyter/").
- `README.md`: nota curta (relatórios markdown são o caminho atual; notebooks
  legados arquivados).
- **`garmindb/GarminDB_Comprehensive_Documentation.md`**: atualizar/remover as
  refs a `Jupyter/` (estava fora do escopo no plano antigo).
- **Não** criar docs novos além de `docs/notebooks/README.md`.
- *(Considerar fundir B+E num commit para não deixar refs órfãs no meio do
  histórico.)*

---

## §7 — Fase SEPARADA (NÃO neste plano)
- Unificar acesso a dados sob `HealthRepository` (**confirmado**: `DecouplingAnalyzer`
  e `db_metrics` abrem `sqlite3` direto; `PowerAnalyzer` lê JSON do filesystem).
- Extrair utilitários markdown compartilhados — **nuance verificada:** a dup do
  formatador pt-BR (`_num`/`w`, `_NO_VALUE`, ícones de tendência) é entre **2 dos
  3** renderers (`performance_renderer` + `longitudinal_renderer`); `renderer.py`
  é em inglês e compartilha pouco. Não assumir contrato comum aos 3.
- ⚠️ **Correção:** a premissa antiga de "dead code (`HourlyStressPattern`,
  `Presenter.render_sleep`)" está **ERRADA** — ambos são **vivos**
  (`HourlyStressPattern` instanciado em `stress_analyzer`, exportado, campo
  tipado; `render_sleep` chamado em `renderer.py:44` e testado). Remover quebraria
  saída + testes. A única observação válida: `hourly_patterns` é **computado mas
  nunca renderizado** (campo populado sem leitor). Reavaliar com cuidado.

## Verificação / aceitação (refeita — critérios concretos)
- [ ] `make flake8` limpo **após ampliar o alvo** para `analysis/`, `data/`,
      `presentation/`, `scripts/`.
- [ ] `make -C test all` (inclui `analysis`): **0 failures, 0 errors, 0 erros de
      coleta**. Baseline de contagem fixada via `pytest --collect-only` (substitui
      o "≈ 110 passed", que era estimativa e na verdade são ~215 funções `test_`).
- [ ] `make verify_commit` verde **num ambiente CI-like limpo** (sem
      `~/HealthData/`, sem `~/.GarminDb/`) — prova que o split safe/manual está certo.
- [ ] `pip install dist/*.whl` em venv novo + `python -c "import garmindb.analysis,
      garmindb.data, garmindb.presentation"` OK (prova o fix do `setup.py`).
- [ ] `git ls-files '*GarminConnectConfig*.json' | grep -v '\.example$'` retorna
      vazio (substitui `grep -i config`, que dava 3+ falsos positivos).
- [ ] `grep -rn "Jupyter/" --exclude-dir=.git .` retorna só refs em
      `docs/notebooks/` (nenhuma ref viva a `Jupyter/` nem aos scripts movidos).

## Commits & push
- Branch **a partir de `develop`**; adicionar-se a `contributors.txt`.
- Commits atômicos por workstream, na nova ordem **A → C → B → D → E** (considerar
  fundir B+E). **Não** dar push sem aprovação explícita; após verde local
  (em env limpo), perguntar antes de `git push`.

## Riscos
- **Empacotamento (`setup.py packages`)**: corrigir antes de C, senão CI quebra no
  import — validar com install não-editable da wheel.
- **Coleta pytest (dois `models.py`)**: rodar por-arquivo ou `importmode=importlib`.
- **Testes com dep de config/DB real** (`test_integration` et al.): isolar em
  `manual`, fora do `verify_commit` — é o risco real (não os testes de auth, que
  são mockados).
- **Refs `Jupyter/` órfãs no Makefile** (`remove_deps`, `clean`): grep o Makefile
  inteiro, não só os 5 alvos óbvios.
- `verify_commit` mais pesado no CI → aceitável; é o objetivo (cobertura real).
