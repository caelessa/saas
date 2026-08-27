FROTA FÁCIL — RC UNIFICADA / CORREÇÃO DO PORTAL

CAUSA DO ERRO 500 NO PORTAL
A RC anterior do envio automático do contrato foi baseada em um app.py anterior e perdeu:
- histórico do veículo no Portal do Proprietário
- rota da identidade visual (logo/favicon)

Os templates atuais dependem dessas rotas e por isso o Portal podia retornar Internal Server Error.

ESTA RC PRESERVA
- Portal do Proprietário
- Histórico do veículo no portal
- Impressão / Salvar PDF
- Personalização visual por tenant
- Logo, favicon, cores
- Acesso separado do proprietário

E MANTÉM
- correção do template de contrato com 5 parâmetros
- envio automático do contrato pelo WhatsApp após geração
- proteção contra envio automático duplicado
- falha do WhatsApp não desfaz o contrato criado

INSTALAÇÃO
1. Substitua somente app.py por este arquivo.
2. Mantenha os templates da RC de personalização/histórico que já estão no Render.
3. Mantenha services/ atuais.
4. Deploy/restart.
5. Teste primeiro /portal-proprietario.
6. Depois gere um contrato novo e valide o envio automático.
