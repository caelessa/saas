FROTA FÁCIL - RC ENVIO AUTOMÁTICO DE VISTORIA POR WHATSAPP

Base: FROTA_FACIL_HOTFIX_LINK_PAGAMENTO_PUBLICO.zip (base mais recente).

ALTERAÇÕES
- Ao criar uma vistoria, o link é enviado automaticamente pela WhatsApp Business Platform.
- Usa o template de vistoria configurado em Configurações > Integrações > WhatsApp.
- Parâmetros enviados exatamente na ordem do template aprovado:
  {{1}} nome do motorista
  {{2}} veículo (marca/modelo)
  {{3}} placa
  {{4}} link público da vistoria
- O envio é registrado em MessageQueue/MessageEvent.
- Se o WhatsApp falhar, a vistoria continua criada e é mostrado um aviso.
- Ao rejeitar uma vistoria e gerar novo link de regravação, o novo link também é enviado automaticamente.
- O botão/manual via WhatsApp Web pode continuar como fallback.

INSTALAÇÃO
1. Substitua apenas app.py pelo arquivo desta RC.
2. Mantenha todos os templates e services atuais.
3. Faça deploy/restart no Render.
4. Confirme que o provedor está como WhatsApp Business e que inspection_template_name aponta para o template aprovado.
5. Crie uma nova vistoria para testar.
