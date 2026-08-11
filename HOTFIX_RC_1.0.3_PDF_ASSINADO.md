# Hotfix RC 1.0.3 — PDF assinado

## O que muda
- Ao concluir a assinatura eletrônica local, o Frota Fácil mantém o PDF original e gera um segundo PDF com a assinatura visual.
- O PDF assinado é salvo no Cloudflare R2 e cadastrado na Central de Documentos como `Contrato Assinado`.
- A página pública passa a exibir/baixar automaticamente a versão assinada depois da assinatura.
- Na tela interna do contrato aparecem botões separados para `PDF assinado` e `PDF original`.
- O modelo TXT pode usar o marcador `{{assinatura_motorista}}` em uma linha isolada para posicionar a assinatura. Se o marcador não existir, o sistema cria automaticamente uma página final de assinatura.

## Migração
Automática no deploy. São adicionadas à tabela `contract`:
- `arquivo_pdf_assinado`
- `hash_documento_assinado`
- `documento_assinado_id`

Nenhum dado existente é removido.

## Teste recomendado
1. Gere um contrato novo.
2. Envie pelo WhatsApp e abra o link no celular.
3. Assine e confirme.
4. Reabra/atualize a página pública: ela deve mostrar o PDF assinado.
5. Na tela interna do contrato, teste `Baixar PDF assinado` e `PDF original`.
6. Confira a Central de Documentos: devem existir o contrato original e o contrato assinado.
