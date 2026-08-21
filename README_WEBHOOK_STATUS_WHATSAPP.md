# Hotfix — status real de entrega WhatsApp

Arquivos: `app.py` e `templates/integracoes.html`.

O hotfix adiciona `/webhooks/whatsapp` para verificação e recebimento dos callbacks da Meta.
Mapeia `sent` → Enviada, `delivered` → Entregue, `read` → Lida e `failed` → Falhou, preservando o motivo de erro.

## Após o deploy
1. Abra Integrações e confira a URL de callback e o Verify Token.
2. Na Meta, configure o webhook do WhatsApp com esses dois valores.
3. Assine o campo `messages`.
4. Envie uma solicitação de KM e acompanhe o histórico.

O Access Token não é exibido nem enviado ao navegador por esta função.
