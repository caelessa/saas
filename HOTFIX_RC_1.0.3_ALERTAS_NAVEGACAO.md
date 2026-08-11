# Hotfix RC 1.0.3 — Navegação da Central de Alertas

## Correção
O botão **Abrir** agora resolve o destino pelo tipo e ID da entidade do alerta.

- Troca de óleo → abre diretamente o veículo correspondente, com a seção Troca de óleo destacada.
- Manutenção → abre Manutenções e posiciona/destaca o registro correspondente.
- Contrato → abre diretamente o contrato correspondente (preparação para alertas futuros).
- Alertas antigos continuam usando `action_url` como fallback.

## Importante
**Marcar como lido** apenas registra que o alerta foi visto. Isso não o resolve. O alerta permanece ativo enquanto a condição que o originou existir e será encerrado automaticamente quando a causa deixar de existir.
