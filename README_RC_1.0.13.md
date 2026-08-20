# Frota Fácil RC 1.0.13 — WhatsApp Embedded Signup (preparação)

## Objetivo
Adicionar o onboarding simplificado da WhatsApp Business Platform sem remover a configuração manual já validada.

## O que entrou
- Botão **Conectar meu WhatsApp** quando as variáveis Meta estiverem configuradas.
- Facebook JavaScript SDK + Embedded Signup usando Configuration ID.
- Backend troca o `code` de autorização por Access Token sem expor o App Secret ao navegador.
- Captura/descoberta de WABA ID e Phone Number ID e gravação isolada no `Integration` do tenant atual.
- Configuração manual preservada em **Configuração avançada / manual**.
- Desconexão local não exclui WABA/número na Meta.

## Variáveis no Render
- `META_APP_ID`
- `META_APP_SECRET`
- `META_WHATSAPP_CONFIG_ID`
- `META_GRAPH_VERSION` (opcional; padrão `v23.0` nesta base)

## Importante antes de produção
A configuração do App Meta precisa estar concluída para Embedded Signup. Para release, a Meta exige configuração do app e permissões/Advanced Access aplicáveis (incluindo business_management e whatsapp_business_management), além de HTTPS e Webhooks conforme o fluxo.

Esta RC prepara e implementa o fluxo no Frota Fácil, mas não inventa nem automatiza a configuração externa do App Meta.
