"""Serviços centrais da Sprint 0.9.2A para contratos."""
from datetime import datetime


def gerar_numero_contrato(contract_id: int, criado_em=None) -> str:
    """Gera número estável e único usando o ID persistido do contrato."""
    if not contract_id:
        raise ValueError("O contrato precisa estar persistido antes da numeração.")
    data = criado_em or datetime.utcnow()
    return f"CTR-{data.year}-{int(contract_id):06d}"


def registrar_evento_contrato(
    session, event_model, *, tenant_id: int, contract_id: int, user_id: int | None,
    evento: str, descricao: str | None = None, status_anterior: str | None = None,
    status_novo: str | None = None,
):
    """Acrescenta um evento à trilha de auditoria na mesma transação."""
    registro = event_model(
        tenant_id=tenant_id, contract_id=contract_id, user_id=user_id,
        evento=evento, descricao=descricao, status_anterior=status_anterior,
        status_novo=status_novo,
    )
    session.add(registro)
    return registro
