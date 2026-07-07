# Mapeamento Completo do Menu Lateral — Garmin Connect

_Referência consolidada para orientar agentes na exportação/construção de dashboards._

---

## 1. Início / Desafios / Calendário / Feed de notícias

Itens de nível único — home, desafios de comunidade, calendário de atividades/treinos e feed social.

## 2. Atividades

Passos, Andares, Minutos de intensidade, Todas as atividades.

## 3. Estatísticas de saúde

Sono, Status de saúde, Peso, Pressão sanguínea, Oximetria de pulso, Aclimatação com oximetria de pulso, Respiração, Frequência cardíaca, Idade do condicionamento físico, Estresse, Body Battery, Resumo de saúde.

## 4. Nutrição

Nutrição, Hidratação.

## 5. Estatísticas de desempenho

Status de treinamento, Disposição, Status de VFC, Previsão de corrida, VO2 Máx., Efeito de treino, Curva de potência, FTP, Velocidade crítica de natação, Limiar de lactato, Pontuação em resistência, Pontuação em subida, Estresse na variação da frequência cardíaca.

## 6. Golfe

Cartões de pontuação, Estatísticas de desempenho, Estatísticas do campo, Tabelas de classificação.

## 7. Treinam. e Planej

Exercícios, Planos Garmin Coach, Corridas e Eventos, Percursos, Estratégias de ritmo PacePro, Guia de potência, Segmentos, Garmin Trails, Heatmap de popularidade, Jet Lag Adviser.

## 8. Equipamento

Link direto — gestão de dispositivos/acessórios.

## 9. Insights

Benchmarking social (você vs. outros usuários Garmin, filtrável por sexo/faixa etária, histórico mensal). Categorias disponíveis via "Personalizar lista": Passos, Sono, Ciclismo, Andares, Corrida, Natação, Natação em alto mar.

## 10. Relatórios (detalhado e verificado subseção por subseção)

Cada subcategoria abaixo foi confirmada clicando individualmente. A maioria segue o padrão "lista de métricas" (cada métrica é um relatório próprio, com filtro de 7 dias/4 semanas/6 meses/1 ano e exportação); duas categorias (Pilates e Treino de força) usam um formato diferente.

### Todas as atividades

Atividades, Calorias ingeridas, Calorias na atividade, Calorias restantes, Distância total, Estresse na variação da frequência cardíaca, Frequência cardíaca máxima, Frequência cardíaca média, Idade do condicionamento físico, Pontuação em resistência, Ritmo médio, Status de treinamento, Status de VFC, Tempo total de atividade, Velocidade média.

### Respiração

Frequência cardíaca média, Frequência respiratória média, Tempo total de atividade.

### Meditação

Frequência cardíaca média, Frequência respiratória média, Tempo total de atividade.

### Esportes de inverno

Atividades, Calorias na atividade, Distância total, Potência média, Tempo total de atividade, Velocidade média.

### Ciclismo

Atividades, Cadência média de bicicleta, Calorias na atividade, Curva de potência, Distância total, Efeito de treino, Frequência cardíaca máxima, Frequência cardíaca média, FTP, Normalized Power®, Potência média, Potência média máxima em 20 minutos, Status de treinamento, Status de VFC, Subida total, Tempo total de atividade, TSS®/IF®, Velocidade média, VO₂ máximo (Ciclismo).

### Jogos

Estresse, Impacto de Body Battery, Taxa de vitória.

### Saúde e boa forma

Aclimatação com oximetria de pulso, Andares subidos, Calorias, Estresse, Frequência cardíaca em repouso, Hidratação, Minutos de intensidade, Oximetria de pulso, Passos, Respiração.

### Pilates _(formato especial)_

Não abre uma lista de métricas — leva direto a um relatório único (como "Todas as atividades"). No teste, não havia dados suficientes para confirmar se existe um seletor de exercícios/músculos como em "Treino de força".

### Corrida

Atividades, Cadência média de corrida, Calorias na atividade, Comprimento médio de passos, Distância total, Efeito de treino, Frequência cardíaca máxima, Frequência cardíaca média, Limiar de lactato, Oscilação vertical média, Percentagem média de tempo de contato com o solo, Pontuação em subida, Previsão de corrida, Proporção de média vertical, Ritmo médio, Status de treinamento, Status de VFC, Subida total, Tempo médio de contato com o solo, Tempo total de atividade, Velocidade média, VO₂ Máximo.

### Natação

Atividades, Calorias na atividade, Distância total, Frequência cardíaca máxima, Frequência cardíaca média, Média de braçadas, Média Swolf, Ritmo médio, Tempo total de atividade, Velocidade crítica de natação.

### Treino de força _(formato especial — confirmado)_

Não é uma lista de métricas simples. Tem duas visualizações: **Exercícios** e **Músculos primários**, com um seletor ("Todos os exercícios" / "Todos os músculos primários") e gráfico de **Repetições** e **Volume (kg)** ao longo do tempo, além da lista de atividades de força realizadas.

### Ioga

Atividades, Calorias na atividade, Tempo total de atividade _(não confirmado individualmente — herdado da extração original; pode compartilhar o formato especial de Pilates/Treino de força)_.

### Resumo do progresso _(dashboard mais amplo — confirmado)_

Diferente das demais: é um painel agregador com filtro por tipo de atividade (cobre toda a taxonomia de esportes do Garmin — corrida, ciclismo, natação, esportes aquáticos, esportes de equipe, esportes com raquete, etc.), agrupamento por semana/mês/ano, período customizável, e totais consolidados: Atividades, Distância total, Tempo total de atividade, Calorias na atividade, Subida total, Velocidade média, Frequência cardíaca média, Cadência média de corrida, Cadência média de bicicleta. Possui **"Exportar para CSV"** e **"Personalizar gráficos"** — provavelmente o ponto de exportação mais poderoso de toda a plataforma.

## 11. Amigos / Grupos

Recursos sociais.

## 12. Medalhas / Recordes pessoais / Objetivos

Gamificação e metas pessoais.

## 13. Precisão do reg. de ativ

Link externo (disclaimer legal da Garmin) — não é dado de dashboard.

---

### Notas para os agentes

Relatórios individuais (Ciclismo, Corrida, Natação, etc.) são a fonte mais granular, cada métrica com botão "Exportar" próprio. "Resumo do progresso" é o melhor ponto de partida para exportação em massa via CSV, cobrindo todos os tipos de atividade de uma vez. "Pilates" e "Treino de força" fogem do padrão de métricas cardio/distância e usam o modelo de séries/repetições — vale testar com dados reais de treino de força para confirmar o schema de exportação desses dois.
