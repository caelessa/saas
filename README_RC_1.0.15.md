# Frota Fácil RC 1.0.15 — Pendências Semanais + Proprietários

Principais mudanças:
- antigo módulo **Investidores** passa a ser apresentado como **Proprietários**, reaproveitando a mesma tabela/estrutura para evitar migração destrutiva;
- proprietário selecionado no veículo passa a preencher `proprietario_legal` e `cpf_cnpj_proprietario`;
- nenhuma das rotinas alteradas força WhatsApp Web/Business: o provedor é lido da integração do tenant;
- automação configurável por tenant (padrão segunda 07h–20h, intervalo 1h);
- cobrança semanal permanece pendente e é reenviada por hora enquanto não houver baixa;
- botão **Dar baixa** encerra lembretes; **Reabrir** reativa;
- solicitação de KM/foto é reenviada no mesmo intervalo enquanto o `MileageRequest` estiver pendente;
- cálculo de excesso de KM continua congelado no `BillingAudit`;
- webhook Meta atualiza o status da cobrança auditada;
- alertas automáticos passam a respeitar a chave de automação do tenant;
- correção: cálculo de cobrança em job não depende mais de `current_user` para buscar odômetros.

## Arquivos a substituir/adicionar
- `app.py`
- `templates/base.html`
- `templates/investidores.html`
- `templates/veiculos.html`
- `templates/editar_veiculo.html`
- `templates/confirmar_veiculo.html`
- `templates/cobrancas.html`
- `templates/integracoes.html`
- `templates/sobre_empresa.html` (preservado)

## Para o envio realmente automático
O endpoint `/jobs/processar-mensagens` precisa ser chamado periodicamente (idealmente a cada hora) com `AUTOMATION_JOB_TOKEN`. A rotina verifica internamente o dia e a janela configurados.

## Observação importante
Quando o tenant estiver configurado em WhatsApp Web, envio automático em segundo plano não é possível; o fluxo manual continua disponível. Com Business Platform, os disparos são automáticos.
