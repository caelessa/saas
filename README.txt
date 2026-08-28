FROTA FÁCIL — RC AUTOMAÇÕES EM CONFIGURAÇÕES

Base: FROTA_FACIL_RC_COMPROVANTES_E_DASHBOARD_LOCADORA_CORRIGIDO.zip

Alterações:
- Central de Configurações com card "Automações e mensagens".
- Tela /configuracoes/automacoes restaurada/incluída no pacote.
- Frequência das mensagens fica em Configurações > Automações.
- Campos: dia da semana, hora inicial, hora final e repetição a cada N horas.
- Controles para KM/foto, cobrança e alertas automáticos.
- Botão de processamento manual para teste.
- Validação de horários e limites dos campos.
- Integrações continua destinada à conexão WhatsApp/Meta, templates e testes.
- Nenhuma migração de banco de dados necessária.
- Mantidas as funcionalidades cumulativas da RC base, inclusive comprovantes de manutenção e dashboards financeiros.

Observação: nesta RC a frequência é uma janela global para as automações existentes, preservando a lógica atual do backend. Separar uma frequência independente para cada tipo de mensagem exige uma evolução adicional do processador e não foi feito silenciosamente nesta correção.
