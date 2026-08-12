"""Automações de comunicação de manutenção.

Cria mensagens imediatas e lembretes agendados. O envio real é delegado ao
CommunicationService, preservando WhatsApp Web como fallback e usando a
WhatsApp Business Platform quando configurada.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def parse_schedule(date_value: str | None, time_value: str | None):
    if not date_value:
        return None
    hhmm = (time_value or "09:00").strip() or "09:00"
    try:
        local = datetime.strptime(f"{date_value} {hhmm}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return local


def maintenance_message(*, driver_name, vehicle, maintenance, reminder=False):
    date_br = "data a definir"
    if maintenance.proxima_data:
        try:
            date_br = datetime.strptime(maintenance.proxima_data, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            date_br = maintenance.proxima_data
    hour = maintenance.proxima_hora or "horário a definir"
    prefix = "Lembrete: sua manutenção é amanhã." if reminder else "Uma manutenção foi agendada para o seu veículo."
    lines = [
        f"Olá, {driver_name}!",
        "",
        prefix,
        f"Veículo: {vehicle.marca_modelo or 'Veículo'} — {vehicle.placa}",
        f"Serviço: {maintenance.tipo or 'Manutenção'}",
        f"Data: {date_br}",
        f"Horário: {hour}",
    ]
    if maintenance.oficina:
        lines.append(f"Oficina/local: {maintenance.oficina}")
    if maintenance.observacoes:
        lines.append(f"Observações: {maintenance.observacoes}")
    lines.extend(["", "Frota Fácil — gestão da sua locadora."])
    return "\n".join(lines)


def reminder_datetime(maintenance):
    scheduled = parse_schedule(maintenance.proxima_data, maintenance.proxima_hora)
    if not scheduled:
        return None
    return scheduled - timedelta(days=1)
