HOTFIX FROTA FÁCIL — TEMPLATE WHATSAPP CONTRATO

Erro corrigido:
(#132000) Number of parameters does not match the expected number of params

Template aprovado:
Olá, {{1}}!

Seu contrato {{2}} referente ao veículo {{3}} — placa {{4}} está disponível.

Acesse o link abaixo para visualizar o documento e realizar a assinatura:

{{5}}

Obrigado.

Parâmetros enviados pelo Frota Fácil:
{{1}} = nome do motorista
{{2}} = número do contrato
{{3}} = marca/modelo do veículo
{{4}} = placa
{{5}} = link público específico do contrato

Também passa a registrar os parâmetros na MessageQueue para auditoria.

INSTALAÇÃO:
- Substituir somente app.py.
- Manter todos os templates e services atuais.
- Fazer deploy/restart.
- Testar novamente o envio do contrato.

IMPORTANTE:
Em Integrações > WhatsApp, o nome do template de contrato deve apontar para o template aprovado na Meta.
