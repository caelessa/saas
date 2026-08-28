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
