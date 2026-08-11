# Frota Fácil — RC 1.0.3

## Central de Alertas e Manutenção Preventiva

Esta versão implementa a infraestrutura inicial da Central de Alertas do Frota Fácil.

### O que mudou

- Manutenções futuras agora geram alertas por **data** e/ou **quilometragem**.
- Cada manutenção permite definir com quantos **dias** e **km** de antecedência o aviso começa.
- Níveis visuais:
  - Verde: em dia.
  - Amarelo: próximo do limite.
  - Vermelho: vencido/atingido.
- Troca de óleo passa a alimentar a mesma infraestrutura de alertas.
- Nova tela **Central de Alertas**.
- Dashboard mostra a quantidade de alertas ativos e os alertas prioritários.
- Uma nova leitura de quilometragem recalcula imediatamente os alertas.
- A rotina é idempotente: atualiza alertas existentes e evita duplicação contínua.

### Como os alertas são recalculados

Nesta RC, os alertas são recalculados quando:

1. o usuário abre o Dashboard;
2. abre Manutenções;
3. abre a Central de Alertas;
4. cadastra uma manutenção;
5. atualiza a quilometragem manualmente;
6. o motorista envia nova quilometragem pelo link público.

Isso garante que, ao acessar o sistema, a situação esteja atualizada. O envio automático em segundo plano/WhatsApp será ligado posteriormente à WhatsApp Business Platform e a um agendador (ex.: Azure Functions).

### Migração

O `seed()` continua executando `migrate_schema()` automaticamente. Serão adicionados, quando ainda não existirem:

- `maintenance.alerta_km_antes`
- `maintenance.alerta_dias_antes`
- campos de rastreamento em `alert` (`source_key`, entidade, ação, atualização e resolução)

Nenhuma exclusão de dados existentes é realizada.
