HOTFIX — Repasse efetivamente pago respeita o veículo filtrado

Correção:
- O cálculo do realizado no Portal do Proprietário agora filtra BillingAudit pelos contract_id dos contratos pertencentes aos veículos efetivamente selecionados.
- A placa histórica da auditoria não é mais usada para decidir a qual veículo o pagamento pertence.
- O filtro por placa continua definindo a lista de veículos e, a partir dela, os contratos elegíveis.
- Reenvios duplicados no mesmo contrato/data continuam consolidados.

Sem alteração de banco de dados.
