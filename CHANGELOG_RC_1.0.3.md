# Changelog — RC 1.0.3

## Adicionado
- `services/alert_service.py`.
- Central de Alertas (`/alertas`).
- Alertas de manutenção por data.
- Alertas de manutenção por quilometragem.
- Configuração de antecedência por manutenção (dias/km).
- Persistência e atualização automática dos alertas.
- Resolução automática quando a condição deixa de existir.
- Navegação para a Central de Alertas.
- Status visual da manutenção (Em dia / Atenção / Vencida).

## Alterado
- Dashboard passa a consumir a Central de Alertas.
- Atualização de km recalcula alertas imediatamente.
- Foto/quilometragem enviada pelo motorista recalcula alertas.
- Troca de óleo passa a criar alerta persistente na Central.

## Compatibilidade
- Mantém contratos, OCR, R2, assinatura, WhatsApp Web e estrutura da RC 1.0.2.
- Inclui o hotfix da solicitação de KM via WhatsApp da RC 1.0.2.
