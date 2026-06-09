## Training Stress Score (TSS)

O **Training Stress Score (TSS)** é uma métrica desenvolvida por Dr. Andrew Coggan e Hunter Allen para quantificar a carga fisiológica de um treino, combinando intensidade e duração em um único número. É amplamente usado no ciclismo, mas também adaptado para corrida, natação e outros esportes.

## O que representa

O TSS fornece uma estimativa do estresse total que um treino impõe ao corpo:
- **TSS = 100**: Equivale a pedalar por 1 hora no seu limiar funcional de potência (FTP)
- **TSS < 150**: Recuperação completa geralmente no dia seguinte
- **TSS 150-300**: Alguma fadiga residual no dia seguinte
- **TSS 300-450**: Fadiga residual por 2 dias
- **TSS > 450**: Fadiga residual por vários dias

## Cálculo do TSS

### Para ciclismo (com potência)

A fórmula original do TSS é:

$$TSS = \frac{duração(seg) \times NP \times IF}{FTP \times 36}$$

Onde:
- **NP (Normalized Power)**: Potência normalizada do treino
- **IF (Intensity Factor)**: Fator de intensidade = NP/FTP
- **FTP**: Functional Threshold Power (potência no limiar funcional)

Simplificando:

$$TSS = \frac{duração(seg) \times (NP)^2}{FTP^2 \times 36}$$

Ou ainda:

$$TSS = \frac{duração(horas) \times IF^2 \times 100}{1}$$

### Para corrida (rTSS)

Para corrida, usa-se o pace normalizado:

$$rTSS = \frac{duração(seg) \times NGP \times IF}{FTP_{pace} \times 36}$$

Onde NGP é o Normalized Graded Pace (pace normalizado considerando elevação).

### Para frequência cardíaca (hrTSS)

Quando só há dados de frequência cardíaca:

$$hrTSS = \frac{duração(seg) \times FC_{média} \times IF_{FC}}{LTHR \times 36}$$

Onde:
- **FC_média**: Frequência cardíaca média
- **LTHR**: Lactate Threshold Heart Rate (FC no limiar de lactato)
- **IF_FC**: Fator de intensidade baseado em FC

## Cálculo da Potência Normalizada (NP)

A NP é calculada para representar melhor o custo fisiológico de esforços variáveis:

1. Calcular média móvel de 30 segundos da potência
2. Elevar cada valor à 4ª potência
3. Calcular a média desses valores
4. Extrair a raiz quarta do resultado

$$NP = \sqrt[4]{\frac{1}{n}\sum_{i=1}^{n}P_i^4}$$

## Exemplo prático

**Treino de ciclismo:**
- Duração: 2 horas
- FTP do atleta: 250W
- Potência Normalizada do treino: 200W

Cálculos:
- IF = 200/250 = 0.80
- TSS = 2 × (0.80)² × 100 = 2 × 0.64 × 100 = 128

Este TSS de 128 indica um treino moderado, com recuperação completa esperada em 24 horas.

## Aplicações práticas

O TSS é usado para:

1. **Periodização do treino**: Planejar cargas semanais e mensais
2. **Monitoramento de fadiga**: Através do ATL (fadiga aguda) e CTL (fitness crônico)
3. **Prevenção de overtraining**: Controlando acúmulo de carga
4. **Tapering**: Redução gradual antes de competições
5. **Comparação entre treinos**: Diferentes durações e intensidades

## Limitações

- Requer medição precisa de FTP/LTHR
- Não considera fatores como calor, altitude, estado nutricional
- Diferentes modalidades têm escalas ligeiramente diferentes
- Não captura completamente o estresse de treinos de força ou técnica

O TSS é uma ferramenta valiosa quando usada em conjunto com outras métricas e percepção subjetiva de esforço para otimizar o treinamento e recuperação.