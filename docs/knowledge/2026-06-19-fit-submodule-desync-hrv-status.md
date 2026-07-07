#needs-peer-review

# `--import` quebra com `AttributeError: FileType has no attribute 'hrv_status'` — submódulo `Fit` ficou atrás do recurso HRV do `garmindb`

**Data:** 2026-06-19
**Contexto:** Update incremental de rotina (`garmindb_cli.py --all --download --import
--analyze --latest`). O download terminou normalmente, mas o **import** abortou ao
processar monitoring:

```
File ".../garmindb/import_monitoring.py", line 75, in __init__
    super().__init__(..., [fitfile.FileType.monitoring_b, fitfile.FileType.hrv_status], ...)
AttributeError: type object 'FileType' has no attribute 'hrv_status'
```

## A Suposição (Myth)

"O repo está consistente: se o pacote `garmindb` usa `fitfile.FileType.hrv_status`,
então o submódulo `Fit` fixado já tem esse membro de enum." E, irmã da nota de
staleness do script: "basta a fonte estar certa para o runtime refletir."

Ambas falsas.

## O Fato (Truth)

1. **Dessincronia de submódulo.** O recurso de HRV entrou no `garmindb` no commit
   `b27b5c7 "Feature/hrv support (#295)"` — que **está na nossa branch** e referencia
   `fitfile.FileType.hrv_status` em `garmindb/import_monitoring.py:75`. Mas o ponteiro
   do submódulo `Fit` no superprojeto estava fixado em `d0f0dfa "build updates"`,
   cujo enum `FileType` (`Fit/fitfile/file_type.py`) **não tem** `hrv_status`. O código
   do pacote ficou à frente do submódulo do qual ele depende.

2. **O upstream do `Fit` já tinha a correção.** O commit `f069cba "Add HRV status file
   type and message type definitions"` adiciona `hrv_status = 68` e é o **filho direto**
   do commit fixado `d0f0dfa`. O tip de `origin/master` (`6272d15 "tested with python
   3.14"`) inclui `f069cba` + `a93c832 (flake8)`. Ou seja: faltava só avançar o ponteiro
   do submódulo quando o recurso HRV foi mergeado.

3. **Dois níveis de staleness, como na nota do script.** Avançar a árvore de trabalho do
   submódulo **não basta**: o `fitfile` é instalado **não-editable** (cópia em
   `.venv/lib/python3.12/site-packages/fitfile`). Foi preciso **reinstalar** para o enum
   atualizado valer em runtime.

## Evidência

- `git merge-base --is-ancestor b27b5c7 HEAD` → HRV support está na branch.
- `git submodule status Fit` → `d0f0dfa9... Fit (1.0.1-62-gd0f0dfa)` (fixado, sem hrv).
- `git -C Fit log --oneline d0f0dfa..origin/master` → `6272d15`, `a93c832`, `f069cba`.
- Antes do reparo: `python -c "import fitfile; print('hrv_status' in dir(fitfile.FileType))"`
  → `False`. Depois da reinstalação → `True FileType.hrv_status`.

## Reparo aplicado nesta sessão

```bash
git -C Fit checkout origin/master            # d0f0dfa -> 6272d15 (inclui hrv_status=68)
.venv/bin/pip install --force-reinstall --no-deps ./Fit
.venv/bin/garmindb_cli.py --all --import --analyze --latest   # import completa, inclui hrv_status:68
```

O import passou a processar `[<FileType.monitoring_b: 32>, <FileType.hrv_status: 68>]`
sem erro. O bump do gitlink (`M Fit`) ficou **não-commitado**, pendente de peer-review.

## Implicação Analítica

- **Correção definitiva sugerida:** commitar o bump do ponteiro do submódulo `Fit` para um
  commit `>= f069cba` (idealmente o tip de `origin/master`, `6272d15`). Sem isso, qualquer
  checkout limpo + `git submodule update` reintroduz o bug em qualquer import de monitoring.
- **Lição transversal:** ao mergear recursos do `garmindb` que dependem de novos
  `FileType`/`MessageType`, é obrigatório avançar o ponteiro do submódulo `Fit` no mesmo PR.
  O CI/testes do pacote não pegam porque a divergência vive na ponte pacote↔submódulo.
- **Operacional:** após qualquer mudança na árvore do submódulo, reinstalar o pacote do
  submódulo no venv (`pip install --force-reinstall --no-deps ./Fit`), pois a instalação é
  cópia, não link — mesmo padrão da nota de staleness dos scripts.
