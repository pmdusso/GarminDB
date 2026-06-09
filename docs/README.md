# docs/

Documentação do fork pessoal do GarminDB. Layout:

| Pasta | O que vai aqui |
|---|---|
| **`reports/`** | Relatórios **gerados** (entregáveis). São saídas recriáveis — veja "Como gerar" abaixo. Mantenha só o relatório vivo; saídas datadas antigas podem ser apagadas (o código as regenera). |
| **`knowledge/`** | Notas conceituais e descobertas duráveis. Notas de descoberta seguem `YYYY-MM-DD-topico.md` e começam com `#needs-peer-review` (revisão humana). Inclui o runbook operacional. |
| **`plans/`** | Design e arquitetura — histórico de *como* o código foi construído (planos de implementação, specs de analyzers, roadmap). Referência, não entregável. |
| **`superpowers/`** | Specs (`specs/`) e planos (`plans/`) gerados pela convenção das skills *superpowers*. Caminho padrão das skills — não mover. |

## Conteúdo atual

- `reports/relatorio-anamnese-2025-2026.md` — **relatório vivo**: visão longitudinal 2025/2026 para anamnese esportiva (médico do esporte).
- `knowledge/2026-06-08-descobertas-dados-anamnese.md` — fatos não óbvios dos dados (sem potência, distância em km, timestamps locais, etc.).
- `knowledge/2026-06-08-reativacao-e-runbook.md` — runbook de operação (manter os dados atualizados).
- `knowledge/TSS.md` — referência sobre Training Stress Score.
- `plans/` — plano de arquitetura em camadas, designs dos analyzers, `NEXT_STEPS.md`, `improvement-plan-reports-dashboards.md`.
- `superpowers/` — spec/plano do relatório de performance.

## Como gerar relatórios

```bash
# Anamnese longitudinal (2025/2026, tendências + totais + triagem de sinais)
python scripts/generate_report.py --anamnesis -o docs/reports/relatorio-anamnese-2025-2026.md

# Performance (snapshot 30 dias rumo à prova) — imprime no stdout por padrão
python scripts/generate_report.py --performance

# Saúde (janela de --period daily|weekly|monthly, ou --start/--end)
python scripts/generate_report.py --period monthly
```

> Os números vão para um médico: tudo é lido das bases reais, sem fabricação. **Não há dados de potência** — FTP/W·kg são metas configuradas, não medições (ver `knowledge/`).

## Convenções

- **Atualize documentos existentes** em vez de criar novas versões datadas. Relatórios gerados são a exceção (são saídas).
- Descobertas novas → `knowledge/YYYY-MM-DD-topico.md` com `#needs-peer-review` no topo; não commitar até revisão humana.
- Planos/specs novos → `superpowers/` (via skills) ou `plans/`.
