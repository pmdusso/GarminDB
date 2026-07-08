# Brainstorm: capturar a cauda longa do FIT + resiliência do pipeline

_Documento de reflexão sobre as ideias **2** e **3** do estudo de `garmin-health-data` e `garmin-givemydata`. **Não é um plano de implementação** — é pra decidirmos se, como e quando. Cheio de perguntas em aberto de propósito._

**Data:** 2026-07-07 · **Status:** rascunho pra discussão

---

## Ideia 2 — parar de perder a cauda longa do FIT

### O problema, medido (não especulado)

O `activity_records` do GarminDB tem **colunas fixas** e captura só: `timestamp, position_lat/long, distance, altitude, speed, hr, cadence, power, rr, temperature`. Tudo que o FIT traz além disso é **descartado silenciosamente**.

Amostrei 8 atividades suas (corrida/ciclismo/natação) e enumerei os campos de `record`. O que está sendo jogado fora, por-segundo:

| Categoria | Campos descartados | Nas quantas atividades |
|---|---|---|
| **Dinâmica de corrida** | `stance_time`, `stance_time_balance`, `stance_time_percent`, `step_length`, `vertical_ratio`, `avg_vertical_oscillation` | 3/8 (todas as corridas) |
| **Dinâmica de ciclismo (pedal)** | `left_right_balance`, `left/right_pedal_smoothness`, `left/right_torque_effectiveness`, `accumulated_power` | 1–4/8 |
| **Fisiológico em atividade** | `respiration_rate` (por-segundo), `fractional_cadence`, `grade` | 3–4/8 |
| **Não-documentados** | `unknown_87/107/134/135/136/137/138/140/143/144` | 3–6/8 |

> Ressalva de leitura: `heart_rate` aparece como "não capturado" na sonda, mas é só nome — o GarminDB renomeia `heart_rate`→`hr`. HR **está** capturado. O acima é o que realmente some.

### A distinção que muda tudo

As **médias por atividade** das dinâmicas de corrida (`avg_vertical_oscillation`, `avg_ground_contact_time`, `avg_step_length`, `avg_vertical_ratio`) **já existem** em `steps_activities`. O que se perde é a **série por-segundo** — a variação dessas métricas ao longo do treino.

Então a pergunta real não é "perco dinâmica de corrida?" — é **"preciso da série por-segundo, ou a média por atividade basta?"**. Isso decide se há problema a resolver.

Contraponto ao Stryd: lá os campos dev eram **zeros**, então não valia nada. Aqui os campos nativos (`stance_time`, `left_right_balance`, `respiration_rate`) têm **valor real** — se você quiser, por exemplo, ver a assimetria de pedal degradar num treino longo, ou a cadência de respiração subir num intervalado, só a série entrega.

### Opções sobre a mesa

| # | Abordagem | O que é | Prós | Contras |
|---|---|---|---|---|
| **2a** | Side-table EAV | `supplemental_activity_metric(activity_id, timestamp, name, value, units)` — captura todo campo numérico *não-mapeado* do record | Aditivo, não toca schema existente; pega a cauda inteira de graça, inclusive `unknown_*` futuros | 10-20× linhas; tudo vira FLOAT; precisa política de retenção; `unknown_*` sem semântica |
| **2b** | Coluna `raw_json` gêmea | Guardar o JSON/frame cru ao lado das colunas typed | Future-proof; reprocessa sem re-baixar | Não casa bem com FIT binário (é o padrão do givemydata pros endpoints **JSON**, não pra records); incha texto |
| **2c** | Colunas dedicadas | ALTER pra adicionar `stance_time`, `left_right_balance`, etc. onde interessa | Typed, consultável, compacto | Volta à esteira "ALTER por métrica"; escolhe vencedores; `unknown_*` continua perdido |
| **2d** | Status quo | Não fazer nada | Zero custo/risco; médias já cobrem muito | Perde a série por-segundo pra sempre (mas os FITs ficam preservados, dá pra reprocessar depois) |

### Perguntas em aberto (pra refletir)

1. **Granularidade:** o sistema a jusante quer a série por-segundo de dinâmica, ou a média por atividade (que já temos) resolve os segmentos que você imagina?
2. **Quais métricas** de fato? Dinâmica de corrida? Pedal? `respiration_rate` em atividade? Ou "tudo, por via das dúvidas"? Quanto mais específico, mais 2c faz sentido; "tudo" empurra pra 2a.
3. **Os `unknown_*`** — vale gastar tempo decodificando (podem ser métricas Firstbeat: Body Battery em atividade, etc.)? Ou ignorar?
4. **Onde plugar:** plugin (como o Stryd, isolado, sem tocar o core) ou no `ActivityFitFileProcessor`? Plugin é mais preguiçoso e reversível.
5. **Custo de disco:** `activity_records` já tem 4.85M linhas. Uma EAV multiplicaria por ~10×. Aceitável ou precisa de `downsample`/`prune` (ideia do health-data) junto?
6. **Retroatividade:** como os FITs ficam preservados, qualquer opção pode fazer backfill via `--rebuild_db`. Isso muda a urgência? (pode-se decidir depois sem perder histórico.)

### Leitura preguiçosa (não é decisão, é ponto de partida)

O caminho de menor arrependimento é **medir a necessidade antes de construir a captura**: escolher 1–2 análises concretas que o sistema a jusante faria com a série por-segundo. Se nenhuma aparece, é 2d (as médias bastam) e os FITs seguem lá pra quando aparecer. Se aparecer, **2a como plugin** (não toca o core, backfill via rebuild) é o mínimo que pega a cauda inteira — com a ressalva de já pensar retenção junto, senão o disco vira problema.

---

## Ideia 3 — resiliência do pipeline

São **dois pedaços separáveis** que o estudo juntou, mas que têm urgências bem diferentes pra você.

### 3a — ciclo de vida / quarentena / recuperação de crash

**O que o health-data faz:** pastas `ingest/process/storage/quarantine`, um dia ruim vai pra quarentena e o resto continua, crash recupera movendo `process/`→`ingest/`.

**O que o GarminDB já tem:** preserva os arquivos baixados em `~/HealthData/FitFiles/` e permite `--rebuild_db`. Ou seja, já há um "storage" e um caminho de reprocessamento.

**O que falta:** isolamento por-arquivo (quarentena) e recuperação de crash no meio do import.

**A pergunta honesta:** com que frequência o import falha *pra você*, e o modo de falha é isolado ou global?
- O crash que já batemos (desync do submódulo Fit → `AttributeError FileType.hrv_status`) era **global** — quebrava tudo, não um arquivo. Quarentena por-arquivo **não teria ajudado** nesse caso.
- Se as falhas que você vê são majoritariamente globais (ambiente, submódulo, auth), o ciclo de quatro pastas resolve o problema errado.
- Se um dia um FIT corrompido isolado abortar um import inteiro, aí a quarentena paga.

Sem esse dado, 3a é **solução à procura de problema**. Vale primeiro observar: nos últimos imports, houve falha por-arquivo que derrubou o lote?

### 3b — cascata de auth (fallback do garth)

**O que os dois repos fazem:** abandonam garth e vendorizam auth própria (impersonação TLS via curl_cffi, ou navegador real) porque, pra eles, "garth morreu".

**A realidade sua:** medimos hoje — **o garth funcionou**, renovou a sessão de dez/2025 sozinha e baixou tudo no `--latest`. Garth **não** está morto pra você.

**Leitura YAGNI:** 3b é seguro *puro*, pra um cenário que ainda não aconteceu. Construir agora é otimizar pra um incêndio que não começou. O movimento preguiçoso: **documentar o `strategies.py` do health-data como referência de "quebra o vidro em caso de emergência"** (é Apache-2.0, dá pra copiar), e só implementar se/quando o garth realmente parar. Um apontador de 3 linhas no CLAUDE.md ou num knowledge doc resolve por ora.

### Perguntas em aberto (pra refletir)

1. Nos seus imports recentes, alguma falha foi **por-arquivo** (um FIT ruim derrubou o lote)? Ou sempre global?
2. Qual a real probabilidade do garth quebrar no seu horizonte? (baixo, dado que acabou de funcionar.)
3. Se fôssemos fazer *algo* de 3a, o subconjunto mínimo é só **recuperação de crash** (retomar import interrompido) — vale mais que a quarentena?

---

## As decisões que são de fato nossas (resumo dos forks)

1. **Ideia 2:** as médias por atividade bastam (→ 2d, não fazer nada), ou o sistema a jusante precisa da série por-segundo de dinâmica (→ 2a/2c)?
2. **Ideia 2, se sim:** capturar "tudo" via EAV-plugin (2a) ou colunas dedicadas pras métricas que você nomear (2c)?
3. **Ideia 3a:** há dor real de falha por-arquivo, ou o `--rebuild_db` + preservação de FITs já basta?
4. **Ideia 3b:** documentar como fallback (recomendado) ou é prioridade construir agora?

## Próximo passo sugerido (barato, reversível)

Antes de qualquer código: **nomear 1–2 perguntas analíticas concretas** que o sistema a jusante faria e que exigem (a) a série por-segundo de dinâmica e (b) resiliência extra. Se as perguntas existirem, elas escolhem a opção sozinhas. Se não existirem, a resposta preguiçosa correta é 2d + documentar 3b — e os FITs preservados garantem que nada disso é irreversível.
