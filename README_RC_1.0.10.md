# Frota Fácil RC 1.0.10 — Cobrança semanal via WhatsApp Web

## Objetivo
Gerar lembretes semanais de pagamento usando automaticamente os dados do contrato vigente e abrir a mensagem pronta no WhatsApp Web.

## Regras
- Usa motorista, telefone, veículo, dia de vencimento e valor semanal do contrato.
- Se houver pelo menos duas leituras recentes de KM (última leitura em até 10 dias), calcula a diferença entre as duas últimas leituras.
- Quando essa diferença superar o limite semanal do contrato, calcula: km excedente × valor por km excedente e soma ao total.
- Sem histórico recente suficiente, envia somente o valor semanal, conforme solicitado.
- O WhatsApp Web não permite envio servidor-a-servidor automático: o Frota Fácil abre a conversa com a mensagem preenchida e o administrador confirma o envio.
- O histórico registra `ABERTA_NO_WHATSAPP`, sem afirmar falsamente que a mensagem foi entregue.

## Novidades
- Menu `Cobranças`.
- Tela de vencimentos de hoje e todos os contratos semanais vigentes.
- Banner no Dashboard quando há cobranças vencendo hoje.
- Botão para abrir cada lembrete no WhatsApp Web.
- Ajuda contextual para o novo módulo.

## Arquivos alterados/adicionados
- app.py
- templates/base.html
- templates/dashboard.html
- templates/cobrancas.html (novo)
- static/help.js
- static/style.css

Não há migração de banco nesta RC.
