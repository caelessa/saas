# RC 1.0.2 — Central de Comunicação e Provedores de Assinatura

## Implementado

- `CommunicationService` centraliza o envio de mensagens.
- WhatsApp Web permanece como modo padrão e compatível com o fluxo atual.
- Estrutura funcional para WhatsApp Business Platform via Cloud API.
- Fila persistente `message_queue` e eventos `message_event`.
- Histórico de mensagens na tela Integrações.
- Configuração do WhatsApp por locadora (`tenant_id`).
- Teste manual da conexão da WhatsApp Business Platform.
- Abstração `SignatureProviderService` para assinatura local, Clicksign e DocuSign.
- Tela de configuração dos provedores de assinatura por locadora.
- Integrações incluídas no backup lógico do tenant.

## Importante

A integração real de envio de envelopes para Clicksign/DocuSign ainda não foi ativada nesta RC. Esta entrega cria a camada desacoplada e os campos necessários para a próxima implementação, sem remover o fluxo local que já funciona.

As credenciais cadastradas nesta RC ficam no banco da aplicação. Use apenas credenciais de sandbox/teste até implementarmos criptografia ou integração com um cofre de segredos.
