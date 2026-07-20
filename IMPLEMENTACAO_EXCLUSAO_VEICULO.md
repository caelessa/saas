# Exclusão de veículo

Foi adicionada a opção **Excluir** na tabela de veículos.

## Regras de segurança

- A exclusão pede confirmação no navegador.
- Veículos com qualquer contrato vinculado não podem ser excluídos, preservando o histórico jurídico e financeiro.
- Quando permitido, são removidos também os registros de quilometragem, solicitações de km, fotos do painel, manutenções e documentos vinculados ao veículo.
- A exclusão respeita a locadora do usuário autenticado.

## Teste

1. Cadastre um veículo sem contrato.
2. Clique em **Excluir** e confirme.
3. Verifique que ele desapareceu da frota.
4. Tente excluir um veículo com contrato: o sistema deve bloquear e mostrar um aviso.
