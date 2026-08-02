"""Máquina de estados dos contratos e sincronização com o veículo."""
from services.contract_service import registrar_evento_contrato
from services.vehicle_state_service import VehicleStateService, VehicleStateError


class ContractStateError(ValueError):
    pass


class ContractStateService:
    ALLOWED = {
        "Rascunho": {"Gerado", "Cancelado"},
        "Gerado": {"Enviado", "Visualizado", "Assinado", "Cancelado"},
        "Enviado": {"Visualizado", "Assinado", "Cancelado"},
        "Visualizado": {"Assinado", "Cancelado"},
        "Assinado": {"Ativo", "Encerrado", "Cancelado"},
        "Ativo": {"Encerrado", "Cancelado"},
        "Encerrado": set(),
        "Cancelado": set(),
    }

    def __init__(self, session, contract_event_model, vehicle_event_model):
        self.session=session
        self.contract_event_model=contract_event_model
        self.vehicle_states=VehicleStateService(session,vehicle_event_model)

    def transition(self, *, contract, new_status, user_id, now, vehicle_destination="Disponível"):
        old_status=contract.status or "Rascunho"
        if new_status == old_status:
            return contract
        if new_status not in self.ALLOWED.get(old_status,set()):
            raise ContractStateError(f"Transição inválida do contrato: {old_status} → {new_status}.")
        vehicle=contract.vehicle
        driver=contract.driver
        if new_status in ("Assinado", "Ativo"):
            if not vehicle:
                raise ContractStateError("O contrato não possui veículo vinculado.")
            self.vehicle_states.rent(vehicle=vehicle,contract=contract,driver=driver,user_id=user_id,reason=f"Veículo alugado pelo contrato {contract.numero_contrato}.",now=now)
            if not contract.assinado_em:
                contract.assinado_em=now
        elif new_status in ("Cancelado", "Encerrado") and vehicle and vehicle.current_contract_id in (None,contract.id):
            destination = vehicle_destination if new_status == "Encerrado" else "Disponível"
            if vehicle.status in ("Reservado","Alugado","Devolução"):
                self.vehicle_states.release(vehicle=vehicle,contract=contract,driver=driver,user_id=user_id,destination=destination,reason=f"Contrato {contract.numero_contrato} {new_status.lower()}.",now=now)
        contract.status=new_status
        contract.atualizado_em=now
        registrar_evento_contrato(
            self.session,self.contract_event_model,tenant_id=contract.tenant_id,contract_id=contract.id,user_id=user_id,
            evento="STATUS_ALTERADO",descricao=f"Status alterado de {old_status} para {new_status}.",
            status_anterior=old_status,status_novo=new_status,
        ).criado_em=now
        return contract
