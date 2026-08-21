# Frota Fácil RC 1.0.14 — Automação WhatsApp e Auditoria de Cobranças

## Principais mudanças
- Nenhum fluxo novo de WhatsApp fixa Web/Business: o provedor é lido da integração do tenant.
- Cobrança manual agora respeita a integração: Business Platform envia pela API; WhatsApp Web abre a conversa.
- Cobrança semanal automática no dia configurado no contrato (incluindo segunda-feira), apenas quando o tenant usa Business Platform.
- Solicitação automática de KM às segundas-feiras para contratos vigentes, apenas na Business Platform.
- Alertas operacionais automáticos para motorista na Business Platform, com proteção contra repetição no mesmo dia.
- Cálculo de excesso de KM preservado: duas últimas leituras recentes, limite semanal, km excedente x valor por km.
- Nova tabela BillingAudit: snapshot de motorista, veículo, data, valor semanal, KM, limite, excesso, taxa, valor do excesso, total, texto, template, provedor e vínculo com MessageQueue.
- Tela Cobranças ganhou Histórico/Auditoria.
- Integrações ganhou nomes dos templates de cobrança normal e cobrança com excesso.
- Idioma configurado no tenant passa a ser respeitado também pelo serviço genérico e por mensagens agendadas.

## Templates sugeridos
- payment_template_name: lembrete_pagamento_semanal (5 parâmetros: nome, veículo, placa, valor semanal, vencimento)
- payment_excess_template_name: lembrete_pagamento_com_excesso (7 parâmetros: nome, veículo, placa, valor semanal, valor excesso, total, vencimento)

## Automação em produção
O endpoint já existente `/jobs/processar-mensagens` agora também executa KM de segunda-feira, cobranças vencendo no dia e alertas. Ele exige `AUTOMATION_JOB_TOKEN`.
Para funcionar sem alguém abrir o sistema, configure um Cron/monitor externo para chamar esse endpoint periodicamente (recomendado: a cada hora). A proteção de duplicidade evita repetir cobrança/KM no mesmo dia.

## Arquivos a substituir
- app.py
- templates/integracoes.html
- templates/cobrancas.html

A página pública `templates/sobre_empresa.html` está incluída para preservar o hotfix anterior.
