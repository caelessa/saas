# Hotfix KM — Provedor correto + 4 parâmetros

Corrige a solicitação de KM para:
- respeitar o provedor configurado no tenant (`business` -> `whatsapp_business`; `web` -> `whatsapp_web`);
- enviar os 4 parâmetros do template: nome, veículo, placa e link.

Substituir somente `app.py`.
