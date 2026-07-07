#needs-peer-review

# Plugin Stryd não recupera nada: Form Power / Leg Spring Stiffness estão zerados nos FITs

**Data:** 2026-07-07

## Contexto

Investigando "potencial não utilizado" do GarminDB upstream. O sistema de plugins
(`Plugins/*.py`, copiados para `~/HealthData/Plugins/`) captura campos de
desenvolvedor dos FITs que o schema base descarta. O `stryd_zones_plugin` foi o
candidato mais promissor: nossos FITs de corrida contêm campos Stryd, e o app id
bate exatamente (`18fb2cf01a4b430dad66988c847421f4`).

## A suposição (Mito)

Instalar o plugin Stryd + `--rebuild_db` recuperaria retroativamente `form_power`
e `leg_spring_stiffness` (dinâmica de corrida / economia) para ~46% das
atividades — dado físico gravado que estaríamos "perdendo".

## O fato (Verdade)

**Os campos Stryd de desenvolvedor estão todos ZERADOS nos FITs deste usuário.**
O app "Stryd Zones" (Connect IQ data field) está instalado no relógio e *declara*
os campos, mas grava `0.0` em todos os records. A potência de corrida real chega
pelo canal **nativo** `power` (não `dev_power`), que já é capturado em
`activity_records.power`.

## Evidência

- Teste de importação real (1 FIT → DB temporário via `ActivityFitFileProcessor` +
  `PluginManager`): tabela `stryd_zones_records` criada com 1638 linhas, **todas
  com `form_power=0` e `leg_spring_stiffness=0`**.
- Parse bruto (`fitfile.File`, `MessageType.record`): `dev_Form Power`,
  `dev_Leg Spring Stiffness` e `dev_power` = `0.0` em todos os records.
- Amostra de 12 corridas (Fev–Jun 2026): Form Power/Leg Spring/dev_power sempre 0;
  `native power` sempre real (max 543–1111 W).
- Corridas antigas (2022–meados 2023): **nem declaram** os campos Stryd.
- Conclusão: nenhuma corrida do histórico tem Form Power não-zero.

## Implicação analítica

- **Não instalar** o `stryd_zones_plugin` e **não fazer rebuild** por causa dele —
  só adicionaria uma tabela `stryd_zones_records` cheia de zeros (custo alto:
  ~22k FITs, 4.8M records; ganho nulo).
- Potência de corrida para análise já está disponível em `activity_records.power`
  (560.932 registros de corrida não-nulos).
- Regra geral para plugins GarminDB: a presença do *nome* do campo dev num FIT não
  garante *valor*. Sempre validar valores não-zero antes de investir num rebuild.
- Reavaliar apenas se o usuário passar a usar um app Stryd que efetivamente popule
  os campos (ex.: assinatura Stryd ativa, ou o data field configurado corretamente).
