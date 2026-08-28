FROTA FÁCIL — RC DASHBOARD PROPRIETÁRIO: VALORES TEÓRICOS
Data: 27/08/2026

Base usada: app.py atual enviado pelo usuário (app (6).py).

ALTERAÇÕES
- Dashboard do proprietário passa a usar valores teóricos/previstos como visão principal.
- Previsão calculada a partir do valor da locação dos contratos no período.
- Aplica a regra de percentual do proprietário vigente em cada competência.
- Mantém valores efetivamente pagos separados para comparação.
- Gráfico mensal mostra Repasse teórico x Repasse pago x Custos x Resultado teórico.
- Cards por veículo mostram Receita teórica, Repasse teórico, Custos e Resultado.
- Excesso de KM NÃO é projetado, pois depende da quilometragem real; entra apenas no realizado quando pago.
- Não altera banco de dados nem exige migração.

ARQUIVOS PARA SUBSTITUIR
1. app.py
2. templates/portal_proprietario.html

IMPORTANTE
Esta RC foi construída sobre o app.py atual fornecido em 27/08/2026, preservando as demais funcionalidades existentes.
