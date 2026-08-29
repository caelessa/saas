FROTA FÁCIL — RC PORTAL DO MOTORISTA
Base: HOTFIX_ENVIO_AUTOMATICO_PROPRIETARIO validado pelo usuário.

O que foi adicionado
- Portal do Motorista separado do painel administrativo e do Portal do Proprietário.
- Nova tabela DriverAccess, criada automaticamente pelo db.create_all na inicialização (sem SQL manual).
- Convite com link assinado válido por 7 dias.
- Motorista escolhe o e-mail de login e cria a própria senha; senha fica somente em hash.
- Login e logout próprios.
- Tela do portal com: veículo atual, contratos, cobranças/pagamentos, solicitações de KM, vistorias, manutenções e pendências.
- Pendências de KM e vistoria continuam usando os links públicos existentes, sem removê-los.
- Cobranças pendentes com comprovante/link existente podem ser resolvidas pelo portal.
- Gestão manual em /motoristas/portal-acessos: enviar portal, redefinir e bloquear.
- Opção em Configurações > Automações para convite automático no cadastro do motorista.
- Envio manual permanece disponível mesmo com automação ligada.

WhatsApp
O envio usa, por padrão, o template Meta: acesso_portal_motorista
Parâmetros esperados:
1 = nome do motorista
2 = nome da locadora
3 = link de ativação/login

IMPORTANTE
Se o template acesso_portal_motorista ainda não estiver aprovado na Meta, deixe a opção automática DESLIGADA. O portal pode ser instalado sem o template; crie/aprove o template antes de testar o envio WhatsApp.

Arquivos desta RC
- app.py
- templates/configuracoes_automacoes.html
- templates/motorista_acessos.html
- templates/portal_motorista_ativar.html
- templates/portal_motorista_login.html
- templates/portal_motorista.html
- templates do hotfix anterior do proprietário preservados no pacote.
