# Frota Fácil RC 1.0.5 — Conferência de KM + Ajuda Contextual

## Novidades
1. Conferência de KM configurável por locadora.
   - Aceitação automática (mantém comportamento atual).
   - Aprovação manual: motorista envia foto + KM e a leitura fica em "Aguardando conferência".
   - Administrador visualiza a foto, confirma, corrige ou rejeita.
   - A KM oficial e os alertas só são atualizados após aprovação.
2. Ajuda contextual em todos os módulos principais.
   - Botão "? Como usar" no cabeçalho.
   - Central de Ajuda com tutoriais rápidos.
   - Conteúdo centralizado em static/help.js.
3. Mantido o laboratório de OCR do painel da RC anterior.

## Arquivos para o GitHub
Substituir:
- app.py
- templates/base.html
- static/style.css

Adicionar:
- static/help.js
- templates/configuracoes_quilometragem.html
- templates/conferencia_quilometragens.html

O app executa a migração da nova coluna tenant.conferir_km_motorista automaticamente no startup.
