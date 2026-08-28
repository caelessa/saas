FROTA FÁCIL — RC VISTORIA + FOTO DO PAINEL + KM

Base: FROTA_FACIL_HOTFIX_REPASSE_PAGO_FILTRO_ESTRUTURAL.zip

Alterações desta RC:
- Fluxo público de vistoria passa a ter 2 etapas: vídeo + foto do painel/KM.
- Foto do painel é capturada diretamente da câmera já aberta pela vistoria.
- KM é obrigatória e não pode ser menor que a KM atual do veículo.
- Ao concluir, a KM atualiza Vehicle.km_atual e cria registro no histórico Odometer com origem "Vistoria em vídeo".
- Regravação com a mesma KM não duplica o registro de odômetro.
- Foto e KM ficam vinculadas à Inspection e também à InspectionAttempt para preservar auditoria das tentativas.
- Tela administrativa de Vistorias exibe botão "Ver painel" e a KM informada.
- Nova rota autenticada /vistorias/<id>/painel para visualizar a foto.
- Migração automática adiciona os novos campos às tabelas inspection e inspection_attempt; não é necessário executar SQL manual.

Arquivos principais alterados:
- app.py
- templates/vistoria_publica.html
- templates/vistorias.html

Validações executadas:
- python -m py_compile app.py
- parsing Jinja dos templates
- teste de integridade do ZIP
