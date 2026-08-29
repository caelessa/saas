FROTA FÁCIL — HOTFIX REDEFINIR ACESSO DO PROPRIETÁRIO

Base: HOTFIX_ATIVACAO_PORTAL_PROPRIETARIO.

Novidade:
- botão "Redefinir acesso" na tela de acesso do proprietário;
- invalida imediatamente a senha atual;
- envia novo link de ativação pelo WhatsApp;
- proprietário pode escolher novamente o e-mail e criar nova senha;
- mantém o mesmo registro de InvestorAccess (não apaga o vínculo);
- links de redefinição anteriores são invalidados por nonce;
- sem migração de banco.

Para testar com o único proprietário cadastrado:
1. abra Proprietário > Acesso;
2. clique em "Redefinir acesso";
3. confirme;
4. abra no WhatsApp o novo link recebido;
5. escolha e-mail e senha;
6. confirme a ativação e valide a entrada no portal.

Arquivos alterados:
- app.py
- templates/proprietario_acesso.html

Os demais templates do pacote são preservados da base cumulativa.
