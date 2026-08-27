HOTFIX — LINK PÚBLICO DE PAGAMENTO / COMPROVANTE

Objetivo:
Corrigir Internal Server Error ao abrir /pagamento/<token> sem login.

Alterações:
- A página pública não depende mais do base.html administrativo.
- A rota passa explicitamente a locadora (tenant) ao template.
- A tela mostra identidade visual da locadora.
- Mantém upload PDF/JPG/JPEG/PNG/WEBP até 15 MB.
- Mantém o vínculo do comprovante com a cobrança.
- Não altera contratos, KM, portal do proprietário ou WhatsApp.

Instalação:
1. Substituir app.py.
2. Adicionar/substituir templates/enviar_comprovante.html.
3. Manter todos os demais templates e services atuais.
4. Deploy/restart.
5. Abrir novamente um link de pagamento existente.
