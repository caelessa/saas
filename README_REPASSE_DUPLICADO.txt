HOTFIX — REPASSE PAGO DUPLICADO NO PORTAL DO PROPRIETÁRIO

Correções:
1. O portal passa a consolidar BillingAudit duplicadas da mesma cobrança (contrato + data + placa), priorizando um único registro PAGO.
2. Reenvio manual da cobrança no mesmo dia passa a reutilizar a auditoria já existente em vez de criar outra cobrança financeira.
3. Cobrança já baixada como PAGO não é recriada/re-enviada como nova cobrança do mesmo dia.

Objetivo: impedir que um pagamento de R$ 800 com repasse de 82% apareça duas vezes como R$ 1.312 no portal.

Sem alteração de banco de dados.
