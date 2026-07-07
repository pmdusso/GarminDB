#needs-peer-review

# `--rebuild_db` quebra com `KeyError` porque o script no venv fica obsoleto após editar `scripts/`

**Data:** 2026-06-09
**Contexto:** Ao executar `garmindb_cli.py --rebuild_db` (para popular a coluna `power`
do SP1) e `garmindb_cli.py --hrv --download --import` (SP3), o rebuild abortou
imediatamente com `KeyError: <Statistics.hrv: 8>`.

## A Suposição (Myth)

"Como o pacote está instalado em modo *editable* (`pip install -e .`), editar e
commitar `scripts/garmindb_cli.py` é suficiente — o `garmindb_cli.py` que roda no
venv reflete a fonte." E: "o `KeyError: Statistics.hrv` significa que falta a
entrada `Statistics.hrv` no `stats_to_db_map` da fonte."

Ambas falsas.

## O Fato (Truth)

1. **A instalação editable NÃO cobre os scripts.** Em `setup.py` os executáveis são
   declarados via `scripts=['scripts/garmindb_cli.py', ...]` (não `entry_points`/
   `console_scripts`). O modo editable linka apenas o **pacote** `garmindb/` ao
   código-fonte; os arquivos de `scripts/` são **copiados** para `.venv/bin/` no
   momento do install e **não** são atualizados quando a fonte muda. Resultado:
   `.venv/bin/garmindb_cli.py` ficou parado numa versão anterior que **não tinha**
   nem `Statistics.hrv: GarminDb` no `stats_to_db_map` nem o flag `--hrv`.

2. **A fonte está correta.** `scripts/garmindb_cli.py:53` tem
   `Statistics.hrv : GarminDb,` e `:332` define `--hrv`. O bug era 100% da cópia
   obsoleta no venv.

3. **Por que `hrv` dispara o `KeyError`:** o caminho do rebuild monta a lista de DBs
   a deletar com `[stats_to_db_map[stat] for stat in enabled_stats()]`
   (`scripts/garmindb_cli.py:363-365`). O SP3 habilitou `hrv: True` em
   `~/.GarminDb/GarminConnectConfig.json`. Com a cópia obsoleta (sem `hrv` no mapa),
   a list comprehension estoura `KeyError` para qualquer stat habilitada ausente do
   mapa. Sem o SP3, `enabled_stats()` não incluía `hrv` e o bug ficava latente.

4. **Segurança preservada por acidente de ordem:** a exceção ocorre ao **montar a
   lista** (argumento de `delete_dbs`), **antes** de `delete_dbs` rodar. Por isso o
   rebuild falhou sem apagar nenhum `.db` — todos os DBs sobreviveram intactos.
   (Ainda assim, fizemos backup `~/HealthData/DBs_backup_pre-rebuild_*` antes do
   rebuild real.)

## Evidência

- Traceback (run 1): `File ".venv/bin/garmindb_cli.py", line 347, in main ...
  KeyError: <Statistics.hrv: 8>` — note o caminho `.venv/bin/...` e a linha **347**.
- `diff` fonte × instalado em `stats_to_db_map`: a cópia instalada **não** tinha a
  linha `Statistics.hrv : GarminDb,`; `grep -i hrv .venv/bin/garmindb_cli.py` (antes
  do reparo) não retornava nada.
- Números de linha divergentes: `delete_dbs` na linha **347** (instalado) vs **364**
  (fonte) → confirmam binários diferentes.
- `pip show garmindb`: `Version: 3.6.7`, `Editable project location:
  /Users/pmdusso/code/personal/GarminDB` (editable, mas só do pacote).

## Implicação Analítica

- **Após qualquer edição em `scripts/*.py`, é obrigatório reinstalar** para o venv
  refletir a mudança. Editar a fonte + commitar **não basta**. Opções:
  - reinstalar (`make install` / `pip install -e . --force-reinstall --no-deps`), ou
  - rodar a fonte diretamente: `.venv/bin/python scripts/garmindb_cli.py …`.
- O CI/testes que importam o **pacote** `garmindb` não pegam essa classe de bug,
  porque o bug vive no **script** (camada de orquestração da CLI), não no pacote.
  Um smoke test de `--help`/`--rebuild_db` rodando o binário **instalado** pegaria.
- Reparo aplicado nesta sessão: copiamos o corpo de `scripts/garmindb_cli.py` por
  cima de `.venv/bin/garmindb_cli.py` preservando o shebang do venv
  (`#!/…/.venv/bin/python3`). Verificado: `--hrv` presente e `Statistics.hrv` no
  mapa. (Os outros scripts — `garmindb_checkup`, `garmindb_bug_report` — estavam
  idênticos à fonte; só `garmindb_cli` divergia.)

## Possível correção upstream (a discutir)

Migrar de `scripts=[...]` para `entry_points={'console_scripts': [...]}` em
`setup.py` faria o `pip install -e .` gerar *wrappers* que importam o módulo da
fonte — eliminando a divergência. Exigiria adaptar cada script para expor uma
função `main()` importável (o `garmindb_cli.py` já tem `main(argv)`).
