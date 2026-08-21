CORREÇÃO 500 + PÁGINA PÚBLICA META

Causa: o hotfix da página pública foi gerado sobre um app.py anterior e, ao substituir o app.py mais novo, removeu as rotas de diagnóstico/webhook já usadas pelo template de Integrações. Isso provocou BuildError/500 ao abrir /integracoes.

Este pacote usa como base o app.py do hotfix mais recente de Webhook/Status WhatsApp, que já contém:
- 4 parâmetros do template de KM
- provedor correto whatsapp_business
- diagnóstico de templates Meta
- webhook /webhooks/whatsapp e status de entrega

E adiciona apenas:
- /sobre-a-empresa
- templates/sobre_empresa.html

Para corrigir com segurança, substitua:
- app.py
- templates/integracoes.html
- adicione templates/sobre_empresa.html

Mantenha templates/meta_templates.html que já estava no deploy anterior.
