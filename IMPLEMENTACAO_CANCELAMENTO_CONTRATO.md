# Cancelamento de contrato

Foi adicionada a opção **Cancelar contrato** na lista e na tela de detalhes do contrato.

## Regras implementadas

- Apenas contratos com status **Ativo** podem ser cancelados.
- O contrato não é apagado: permanece no histórico com status **Cancelado**.
- A data e a hora do cancelamento são registradas.
- É possível informar um motivo opcional.
- Se o veículo ainda estiver com status **Alugado**, ele volta para **Disponível**.
- Se o veículo já estiver **Inativo**, **Vendido**, **Bloqueado** ou em **Manutenção**, seu status é preservado.
- Um novo contrato só pode ser criado com motorista **Ativo** e veículo **Disponível**.
- O sistema impede dois contratos ativos para o mesmo veículo.

## Banco de dados

A inicialização faz a migração automática das colunas:

- `contract.cancelado_em`
- `contract.motivo_cancelamento`

Não é necessário apagar o banco existente.
