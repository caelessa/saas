FROTA FÁCIL — RC CONVITE DO PORTAL DO PROPRIETÁRIO

Base: RC COMPROVANTES + DASHBOARD LOCADORA CORRIGIDO.
Esta RC é cumulativa e preserva as melhorias anteriores.

NOVO FLUXO
- Em Proprietários > Acesso ao portal, existe "Gerar link de acesso".
- O link é criptograficamente assinado com SECRET_KEY, contém tenant + proprietário + acesso e nonce único.
- Validade: 7 dias.
- O proprietário abre uma página pública com a identidade visual da locadora.
- Ele cria e confirma a própria senha.
- Após ativar, entra automaticamente no Portal do Proprietário.
- O mesmo link deixa de funcionar após a ativação porque a versão do acesso muda junto com a senha.
- Há botão "Copiar link".
- Se o proprietário tiver telefone, há atalho "Enviar por WhatsApp" (abre o WhatsApp com a mensagem pronta).
- O acesso manual por e-mail/senha foi preservado.
- Bloquear/ativar acesso foi preservado.

BANCO DE DADOS
- Não exige migração nem nova tabela.
- Reutiliza InvestorAccess e assinatura temporizada via SECRET_KEY.

ARQUIVOS ALTERADOS/NOVOS
- app.py
- templates/proprietario_acesso.html
- templates/portal_proprietario_ativar.html

ARQUIVOS CUMULATIVOS DA RC ANTERIOR TAMBÉM INCLUÍDOS
- templates/base.html
- templates/comprovantes_manutencao.html
- templates/financeiro_locadora.html
- templates/portal_proprietario.html
- templates/portal_proprietario_historico.html

VALIDAÇÃO
- app.py validado com python -m py_compile.
- templates validados pelo parser Jinja2.


RC AJUSTE CONVITE AUTOMATICO / SEM EXPIRACAO
- Convite do Portal do Proprietario nao expira por tempo.
- Continua sendo de uso unico: apos definir senha, o token deixa de ser valido.
- Gerar novo convite invalida o anterior quando o acesso ainda nao foi ativado.
- Ao gerar o link, se WhatsApp Business estiver conectado e o proprietario tiver telefone valido, o sistema tenta enviar automaticamente pela Cloud API.
- Nao abre WhatsApp Web.
- Template esperado por padrao: convite_portal_proprietario (pt_BR).
- Parametros do BODY: 1 nome do proprietario, 2 nome da locadora, 3 link de ativacao.
- Se o template ainda nao estiver aprovado/configurado na Meta, o link e gerado normalmente e o sistema informa a falha do envio.
- Sem migracao de banco.
