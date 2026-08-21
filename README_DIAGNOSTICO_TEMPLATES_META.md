# Hotfix diagnóstico de templates Meta

Arquivos a substituir/adicionar:
- `app.py`
- `templates/integracoes.html`
- `templates/meta_templates.html` (novo)

Depois do deploy, acesse **Integrações** e clique em **Ver templates disponíveis na Meta**.
A tela consulta diretamente `/{WABA_ID}/message_templates` e mostra nome, idioma/API, status, categoria e ID, comparando com o template de KM configurado no Frota Fácil.

Nenhuma credencial é exibida na tela e nenhuma configuração é alterada.
