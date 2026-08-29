FROTA FÁCIL - HOTFIX ATIVAÇÃO DO PORTAL PELO PROPRIETÁRIO
Base: FROTA_FACIL_HOTFIX_PORTAL_CONTRATO_CANCELADO.zip

O que muda:
- Proprietário sem acesso recebe link individual de ativação pelo WhatsApp.
- Ao abrir o link, escolhe o e-mail de acesso e cria/confirmar a própria senha.
- Se houver e-mail no cadastro do proprietário, ele aparece apenas como sugestão editável.
- A senha é salva somente como hash (generate_password_hash).
- O link assinado expira em 7 dias.
- Depois da ativação, o link não cria outro acesso: encaminha para o login.
- Após ativar, o proprietário já entra automaticamente no portal.
- Para proprietário já ativado, o botão WhatsApp continua enviando o link normal de login.
- Tela de login ganhou instruções claras para primeiro acesso e login normal.
- Não exige migração de banco.
- O template Meta atual acesso_portal_proprietario continua com os mesmos 3 parâmetros: proprietário, locadora e link.

Arquivos a substituir/adicionar:
- app.py
- templates/proprietario_acesso.html
- templates/portal_proprietario_ativar.html (NOVO)
- templates/portal_proprietario_login.html

Não altera as automações de vistoria, cobrança, manutenção ou o hotfix de contrato cancelado.
