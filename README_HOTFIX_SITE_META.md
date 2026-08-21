HOTFIX — Página pública para verificação empresarial Meta

Arquivos:
- app.py
- templates/sobre_empresa.html

Nova URL pública:
https://SEU-DOMINIO/sobre-a-empresa

Variáveis opcionais no Render:
FROTA_FACIL_RAZAO_SOCIAL
FROTA_FACIL_NOME_FANTASIA
FROTA_FACIL_CNPJ
FROTA_FACIL_ENDERECO
FROTA_FACIL_TELEFONE
FROTA_FACIL_EMAIL
FROTA_FACIL_DESCRICAO

Se alguma variável não for preenchida, a página exibe "Não informado" (exceto nome/descrição, que têm fallback).
