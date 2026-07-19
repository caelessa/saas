# Implementação para demonstração

## Novidades
- Criação de conta de locadora com base isolada e limpa por tenant.
- Link público seguro e exclusivo por veículo/motorista.
- Solicitação de quilometragem pelo WhatsApp usando o telefone cadastrado.
- Captura obrigatória da foto do painel pelo celular.
- Validação para impedir quilometragem menor que a leitura atual.
- Atualização automática da quilometragem do veículo.
- Histórico de solicitações e fotos em **Quilometragens**.

## Fluxo de teste
1. Na tela de login, clique em **Criar conta gratuita**.
2. Cadastre a locadora e o usuário administrador.
3. Cadastre um motorista com seu número de WhatsApp.
4. Cadastre um veículo e a quilometragem atual.
5. Em **Veículos**, escolha o motorista e clique em **WhatsApp**.
6. Envie a mensagem aberta pelo WhatsApp.
7. Abra o link no celular, tire uma foto e informe a quilometragem.
8. Consulte o resultado no menu **Quilometragens**.

## Deploy
O `db.create_all()` criará automaticamente a nova tabela `mileage_request` no banco existente. Não é necessário apagar os dados atuais.

Observação: as fotos continuam no filesystem do Render, que é temporário. Para a demonstração funciona; em produção, migrar para Azure Blob, S3 ou Cloudflare R2.
