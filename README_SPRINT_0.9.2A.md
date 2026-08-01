# Sprint 0.9.2A

## Objetivo
Adicionar identidade única, estados operacionais e trilha de auditoria aos contratos sem alterar OCR, R2, quilometragem ou WhatsApp.

## Arquivos alterados
- `app.py`
- `templates/contratos.html`
- `templates/contrato_detalhe.html`
- `static/style.css`

## Arquivo novo
- `services/contract_service.py`

## Banco
A aplicação adiciona automaticamente campos à tabela `contract` e cria a tabela `contract_event`. Contratos existentes recebem numeração ao iniciar.
