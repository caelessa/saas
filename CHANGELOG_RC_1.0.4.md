# Changelog RC 1.0.4

- Motorista automático na solicitação de quilometragem por contrato vigente.
- Fallback manual para veículos sem motorista vinculado.
- Data + horário para manutenção futura.
- Confirmação de manutenção por WhatsApp no momento do cadastro.
- Lembrete agendado 1 dia antes.
- Resolução automática do motorista pelo contrato vigente.
- Botão WhatsApp motorista na Central de Alertas.
- Templates separados de WhatsApp Business para KM e manutenção.
- Fila persistente com parâmetros de templates.
- Worker `process_scheduled_messages.py` para Cron Job / Azure.
- Conversão de custo de manutenção em formato brasileiro (`350,00`).
