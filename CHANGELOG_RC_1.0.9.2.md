# Frota Fácil RC 1.0.9.2

## WhatsApp Business Platform — diagnóstico de destinatário
- Mantém integralmente a vistoria em vídeo/fotos da RC 1.0.9.1.
- Adiciona um template exclusivo para o botão **Testar conexão**.
- O teste passa a registrar o número digitado e o número normalizado enviado à Meta.
- Registra `contacts.input`, `contacts.wa_id` e `messages.id` retornados pela Meta quando disponíveis.
- Exibe o diagnóstico no histórico recente de mensagens.
- Não altera estrutura de banco de dados.

## Arquivos funcionais alterados
- `app.py`
- `templates/integracoes.html`
