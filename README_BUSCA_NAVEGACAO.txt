FROTA FÁCIL — RC BUSCA DE NAVEGAÇÃO

Base: FROTA_FACIL_RC_PORTAL_MOTORISTA.zip

Alteração:
- adiciona campo "Buscar função..." no menu lateral, disponível nas telas internas;
- autocomplete instantâneo sem consultar banco;
- termos alternativos (ex.: portal motorista, KM, cobrança, manutenção, WhatsApp);
- Enter abre o primeiro resultado;
- setas ↑/↓ navegam entre resultados;
- tecla / foca a busca quando não estiver digitando em outro campo;
- não altera banco de dados nem regras de negócio.

Arquivos deste pacote:
- app.py (preservado da RC Portal do Motorista)
- templates/base.html (novo/atualizado com a busca global)
- templates e recursos da RC Portal do Motorista preservados.

Validações executadas:
- python -m py_compile app.py
- parse Jinja dos templates incluídos
- teste de integridade do ZIP
