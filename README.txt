FROTA FÁCIL — RC CUMULATIVA
Comprovantes de Manutenção + Dashboard Financeiro da Locadora

BASE
- Esta RC parte da RC de comprovantes de manutenção, que por sua vez preserva o Dashboard do Proprietário com visões Teórica + Real.
- Não há migração de banco nesta RC.

NOVIDADE 1 — COMPROVANTES DE MANUTENÇÃO
- Mantém anexos de NF, recibos, orçamento, comprovante de pagamento e outros documentos vinculados à manutenção.
- Proprietário pode visualizar os comprovantes das manutenções dos próprios veículos.

NOVIDADE 2 — DASHBOARD FINANCEIRO DA LOCADORA
Novo menu: "Financeiro da locadora"
Nova rota: /financeiro-locadora

Visão TEÓRICA
- Receita teórica da frota com base nos contratos e periodicidade.
- Repasse teórico aos proprietários conforme regra vigente por veículo/competência.
- Receita teórica da locadora.
- Custos de manutenção registrados.
- Resultado teórico da locadora.
- Excesso de KM não é projetado.

Visão REAL
- Receita efetivamente paga.
- Repasse aos proprietários sobre valores pagos.
- Receita real da locadora.
- Custos registrados.
- Resultado real.
- Cobranças pagas incluem excesso de KM quando existente.

GRÁFICOS
- Composição teórica.
- Evolução mensal teórica.
- Composição real.
- Evolução mensal realizada.
- Resultado teórico x real por veículo.
- Tabela detalhada por veículo.

SEGURANÇA DO CÁLCULO
- Veículo sem proprietário: 100% da participação é da locadora.
- Veículo com proprietário utiliza a regra vigente no período.
- Se houver proprietário sem regra de repasse, a competência não é atribuída à locadora e o dashboard mostra um aviso.

ARQUIVOS DESTA RC
- app.py
- templates/base.html
- templates/financeiro_locadora.html
- templates/portal_proprietario.html
- templates/portal_proprietario_historico.html
- templates/comprovantes_manutencao.html

INSTALAÇÃO
Substitua o app.py e os templates incluídos nesta RC, preservando os demais arquivos do projeto.
