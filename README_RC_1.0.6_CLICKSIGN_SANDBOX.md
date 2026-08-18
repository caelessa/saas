# Frota Fácil RC 1.0.6 — Clicksign Sandbox

Base: `saas-main (3).zip` enviada em 17/08/2026.

## O que entrou
- Integração real com Clicksign API v3 (Envelope) no Sandbox.
- Teste de conexão em Integrações.
- Envio de um contrato PDF existente para assinatura.
- Criação de envelope, upload PDF, signatário, requisitos de qualificação e autenticação por e-mail, ativação e notificação.
- Persistência dos IDs do envelope/documento/signatário e status no contrato.
- Botão para consultar status da Clicksign.
- Quando o envelope retornar `closed`, o contrato é promovido para Assinado/Ativo usando o motor de estados existente.
- Workspace Key virou campo legado/opcional (API v3 usa Access Token).
- O botão **Sair** foi preservado em `templates/base.html` e o CSS atual foi mantido integralmente.

## Arquivos alterados
- `app.py`
- `services/signature_provider_service.py`
- `templates/integracoes.html`
- `templates/contrato_detalhe.html`

## Banco
Migração automática adiciona no contrato:
- `clicksign_envelope_id`
- `clicksign_document_id`
- `clicksign_signer_id`
- `clicksign_status`
- `clicksign_sent_at`

## Teste recomendado
1. Clicksign Sandbox: gere um Access Token.
2. Frota Fácil > Integrações > Assinatura: selecione Clicksign, ambiente Sandbox, cole o token e salve.
3. Clique em **Testar conexão Clicksign**.
4. Abra um contrato com PDF gerado.
5. Informe um e-mail acessível do signatário e clique em **Enviar para Clicksign Sandbox**.
6. Abra o e-mail recebido e conclua a assinatura no Sandbox.
7. No Frota Fácil, clique em **Atualizar status Clicksign**.

> O Sandbox é ambiente de desenvolvimento e os documentos de teste não têm valor jurídico.
