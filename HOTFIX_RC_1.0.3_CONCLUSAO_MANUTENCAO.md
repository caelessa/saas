# Hotfix RC 1.0.3 — Conclusão e histórico de manutenção

## O que muda
- Adiciona o botão **Concluir manutenção** nas manutenções ativas.
- Registra data, km, custo, oficina e observações da execução.
- Encerra automaticamente os alertas da manutenção concluída.
- Mantém a manutenção concluída no histórico permanente.
- Registra um evento na linha do tempo operacional do veículo.
- Permite informar a próxima data e/ou quilometragem no momento da conclusão; quando informadas, um novo ciclo de manutenção é criado automaticamente.
- A ficha de histórico do veículo passa a ter uma tabela exclusiva de manutenções concluídas.

## Banco
A migração automática adiciona à tabela `maintenance`:
- `status`
- `oficina`
- `concluida_em`
- `concluida_por_id`

Não remove dados existentes.

## Teste
1. Crie ou abra uma manutenção com alerta ativo.
2. Clique em **Concluir manutenção**.
3. Informe data e km realizadas e confirme.
4. Volte à Central de Alertas e confirme que o alerta desapareceu.
5. Abra o histórico do veículo e confirme a manutenção na tabela e na linha do tempo.
6. Repita preenchendo uma próxima data/km e confirme que um novo ciclo foi criado.
