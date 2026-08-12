# Checklist RC 1.0.4

1. Faça deploy da versão.
2. Abra Veículos e confirme que veículo com contrato vigente mostra o motorista automaticamente em **Solicitar pelo WhatsApp**.
3. Clique no WhatsApp e confirme que o link de KM é endereçado ao motorista do contrato.
4. Cadastre uma manutenção futura com data, horário e **Notificar motorista** marcado.
5. Em WhatsApp Web, confirme que a conversa abre com veículo, serviço, data e horário.
6. Confira em Integrações o registro da mensagem.
7. Cadastre uma manutenção para mais de 24 horas no futuro e deixe **Lembrete 1 dia antes** marcado.
8. Confira que existe uma mensagem `AGENDADA` na fila.
9. Para teste, ajuste `scheduled_at` ou use uma data apropriada e clique **Processar mensagens agendadas agora**.
10. Com WhatsApp Business configurado, confirme envio automático; com Web, confirme status `AGUARDANDO_MANUAL`.
11. Gere um alerta de manutenção/troca de óleo e use **WhatsApp motorista**.
12. Refaça o fluxo principal: contrato, assinatura, KM, alerta e conclusão de manutenção.
