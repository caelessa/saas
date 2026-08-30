FROTA FÁCIL — RC PORTAL DO PROPRIETÁRIO: RENTABILIDADE E INVESTIMENTO
Data: 30/08/2026

BASE CUMULATIVA
- Construída sobre FROTA_FACIL_RC_ASSINATURA_GUIADA.zip.
- Preserva Portal do Motorista, busca global e assinatura guiada.
- Inclui a versão mais recente disponível do template portal_proprietario.html usada nas RCs/hotfixes do Portal do Proprietário.

O QUE ENTRA NESTA RC
1. Comparativo financeiro por veículo no Portal do Proprietário.
2. Filtro existente por veículo/placa e período preservado.
3. Nova tabela com:
   - receita teórica;
   - repasse efetivamente pago;
   - custos;
   - resultado real;
   - capital próprio;
   - ROI do período;
   - rentabilidade média mensal;
   - payback estimado;
   - situação/ranking.
4. Ranking de ROI entre os veículos do proprietário.
5. Identificação de maior rentabilidade, retorno positivo e baixo retorno.
6. Novo gráfico de ROI quando houver dados de investimento.
7. Área “Investimento do veículo”, preenchida pelo proprietário.
8. Campos patrimoniais:
   - data de aquisição;
   - valor de aquisição;
   - capital próprio/entrada;
   - valor financiado;
   - saldo devedor atual;
   - valor de mercado atual.
9. Histórico patrimonial: cada salvamento gera um snapshot.
10. Relatório individual do veículo para o período selecionado.
11. Botão “Imprimir / Salvar em PDF” usando a impressão nativa do navegador.

NOVAS TABELAS
- vehicle_investment
- vehicle_investment_history

Não é necessária migração SQL manual: o app já executa db.create_all() na inicialização e criará as novas tabelas automaticamente.

REGRA DOS CÁLCULOS DE RENTABILIDADE
- Resultado real = repasse efetivamente pago - custos registrados no período.
- ROI do período = resultado real / capital próprio x 100.
- Rentabilidade média mensal = ROI do período / duração aproximada do período em meses.
- Payback = capital próprio / resultado real médio mensal, quando o resultado é positivo.
- ROI sobre aquisição = resultado real / valor de aquisição x 100.

IMPORTANTE
- Os dados patrimoniais são cadastrados pelo proprietário no portal.
- A locadora continua responsável pelos dados operacionais do veículo.
- Veículos sem capital próprio informado continuam funcionando normalmente, mas ROI/payback ficam como pendentes.
- O ranking usa somente veículos com capital próprio informado.

VALIDAÇÕES EXECUTADAS
- python -m py_compile app.py: OK
- Parse dos templates Jinja: OK
- ZIP será testado com unzip -t.
