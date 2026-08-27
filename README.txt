FROTA FÁCIL — RC ENVIO AUTOMÁTICO DO CONTRATO POR WHATSAPP

BASE
- Último hotfix do template de contrato com 5 parâmetros.

NOVO FLUXO
1. Usuário gera o contrato.
2. Frota Fácil salva contrato, PDF, documento e reserva o veículo.
3. Somente depois de o contrato estar salvo, tenta enviar automaticamente pelo WhatsApp Business.
4. Usa o template de contrato com:
   1 = nome do motorista
   2 = número do contrato
   3 = veículo
   4 = placa
   5 = link público do contrato
5. Se enviado, registra o envio e muda o contrato para Enviado quando aplicável.
6. Se o WhatsApp falhar, o contrato NÃO é perdido nem desfeito.
7. O usuário recebe um aviso e pode usar o botão manual de WhatsApp para tentar novamente.
8. Há proteção para não criar um segundo envio automático se já existir envio PENDENTE/AGENDADO/ENVIADO para o mesmo contrato.

PRÉ-REQUISITOS PARA ENVIO AUTOMÁTICO
- WhatsApp Business conectado.
- Template de contrato configurado.
- Telefone válido no cadastro do motorista.
- PDF do contrato gerado.

INSTALAÇÃO
- Substituir somente app.py.
- Manter templates e services atuais.
- Deploy/restart.
- Criar um contrato de teste e verificar se a mensagem chega automaticamente.
