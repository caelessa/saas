# Armazenamento automático de CNH e CRLV

## Novo fluxo
1. O documento enviado para OCR é guardado temporariamente no Cloudflare R2.
2. O usuário confere os dados extraídos.
3. Ao confirmar o cadastro, o motorista/veículo é criado.
4. O documento original é movido para uma chave definitiva no R2.
5. Um registro é criado automaticamente na Central de Documentos.

## Identificadores
- CNH: `CNH-000123-NOME-DO-MOTORISTA-ANO`
- CRLV: `CRLV-000045-ABC1D23-ANO`

## Campos adicionados em Document
- identificador
- numero_documento
- hash_sha256
- status

A migração é executada automaticamente no início da aplicação.
A Central de Documentos também ganhou pesquisa por identificador, número, arquivo, tipo ou entidade.
