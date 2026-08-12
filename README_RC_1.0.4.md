# Frota Fácil — RC 1.0.4
## Automação de quilometragem e manutenção por WhatsApp

Esta RC parte da RC 1.0.3 com PDF assinado e preserva Central de Alertas, histórico e conclusão de manutenções.

### 1. Motorista automático na solicitação de KM
Quando o veículo possui contrato vigente e `current_driver_id/current_contract_id`, o botão **Solicitar KM** usa automaticamente esse motorista e o telefone do cadastro. A seleção manual só aparece como fallback em veículos sem vínculo vigente.

### 2. Manutenção agendada com data e horário
O cadastro de manutenção agora aceita **horário agendado**, oficina/local e duas opções:
- enviar confirmação ao motorista no momento do cadastro;
- enviar lembrete 1 dia antes.

O motorista é obtido automaticamente a partir do contrato vigente do veículo.

### 3. WhatsApp Web x WhatsApp Business Platform
- **WhatsApp Web:** a confirmação imediata abre a conversa com a mensagem pronta; o usuário ainda confirma o envio. Mensagens agendadas ficam como `AGUARDANDO_MANUAL`, pois WhatsApp Web não suporta disparo servidor-servidor.
- **WhatsApp Business Platform:** confirmação imediata e lembrete agendado podem ser enviados automaticamente, desde que a integração e os templates aprovados estejam configurados.

### 4. Fila e Cron
O lembrete de 1 dia antes é salvo em `message_queue.scheduled_at`.
Para execução sem intervenção, configure um Cron Job para rodar periodicamente:

```bash
python process_scheduled_messages.py
```

Sugestão de frequência: a cada 15 minutos.

Também existe um botão em **Integrações > Fila de automações** para processar mensagens agendadas manualmente durante os testes.

### 5. Templates WhatsApp Business
A tela Integrações ganhou campos separados para:
- contrato;
- solicitação de KM;
- manutenção agendada;
- lembrete de manutenção;
- idioma dos templates.

Os templates devem ser criados/aprovados na conta da Meta antes do uso em produção.

### 6. Alertas -> WhatsApp motorista
Alertas de manutenção e troca de óleo agora possuem ação **WhatsApp motorista**. O motorista é resolvido pelo contrato vigente do veículo.

### Migração
A migração automática adiciona:
- `maintenance.proxima_hora`
- `maintenance.notificar_motorista`
- `maintenance.lembrete_um_dia`
- `maintenance.notificacao_agendamento_id`
- `maintenance.notificacao_lembrete_id`
- `message_queue.template_parameters`

Nenhuma coluna existente é removida.
