# Frota Fácil RC 1.0.11 — Cadastro de motorista

## Alterações
- Corrige o parser da CNH-e para preencher o campo RG quando o OCR já reconhece o documento de identidade.
- Adiciona dois contatos complementares ao motorista.
- Cada contato complementar possui nome, telefone e relação/parentesco.
- Mantém o telefone principal como telefone do próprio motorista e como destino padrão das automações existentes.
- Migração automática adiciona as novas colunas ao banco existente sem apagar cadastros.

## Novos campos
- contato2_nome / telefone2 / contato2_parentesco
- contato3_nome / telefone3 / contato3_parentesco

## Teste de regressão do RG
Validado com o padrão OCR observado na CNH-e enviada: RG 48839639, CPF 38074601870, CNH 05242471403 e categoria AB.
