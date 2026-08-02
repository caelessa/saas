"""Máquina de estados operacional dos veículos."""

class VehicleStateError(ValueError):
    pass


class VehicleStateService:
    ALLOWED = {
        "Disponível": {"Reservado", "Manutenção", "Inativo"},
        "Reservado": {"Alugado", "Disponível", "Manutenção", "Inativo"},
        "Alugado": {"Devolução", "Manutenção"},
        "Devolução": {"Disponível", "Manutenção"},
        "Manutenção": {"Disponível", "Inativo"},
        "Inativo": {"Disponível"},
    }

    def __init__(self, session, event_model):
        self.session = session
        self.event_model = event_model

    def transition(self, *, vehicle, new_status, user_id, now, reason=None, contract=None, driver=None):
        old_status = vehicle.status or "Disponível"
        if new_status == old_status:
            return vehicle
        if new_status not in self.ALLOWED.get(old_status, set()):
            raise VehicleStateError(f"Transição inválida do veículo: {old_status} → {new_status}.")
        vehicle.status = new_status
        vehicle.status_changed_at = now
        vehicle.status_reason = reason
        if new_status in ("Reservado", "Alugado"):
            vehicle.current_contract_id = contract.id if contract else vehicle.current_contract_id
            vehicle.current_driver_id = driver.id if driver else vehicle.current_driver_id
        elif new_status in ("Disponível", "Manutenção", "Inativo"):
            vehicle.current_contract_id = None
            vehicle.current_driver_id = None
        self.session.add(self.event_model(
            tenant_id=vehicle.tenant_id, vehicle_id=vehicle.id,
            contract_id=contract.id if contract else None, driver_id=driver.id if driver else None,
            user_id=user_id, evento="STATUS_ALTERADO", descricao=reason,
            status_anterior=old_status, status_novo=new_status, criado_em=now,
        ))
        return vehicle

    def reserve(self, *, vehicle, contract, driver, user_id, reason, now):
        return self.transition(vehicle=vehicle,new_status="Reservado",user_id=user_id,now=now,reason=reason,contract=contract,driver=driver)

    def rent(self, *, vehicle, contract, driver, user_id, reason, now):
        if (vehicle.current_contract_id not in (None, contract.id)):
            raise VehicleStateError("O veículo já está associado a outro contrato.")
        if vehicle.status == "Disponível":
            self.reserve(vehicle=vehicle,contract=contract,driver=driver,user_id=user_id,reason=f"Reserva automática para {contract.numero_contrato}.",now=now)
        return self.transition(vehicle=vehicle,new_status="Alugado",user_id=user_id,now=now,reason=reason,contract=contract,driver=driver)

    def release(self, *, vehicle, contract, driver, user_id, destination, reason, now):
        if destination not in ("Disponível", "Manutenção"):
            raise VehicleStateError("Destino do veículo deve ser Disponível ou Manutenção.")
        if vehicle.status == "Alugado":
            self.transition(vehicle=vehicle,new_status="Devolução",user_id=user_id,now=now,reason="Devolução iniciada.",contract=contract,driver=driver)
        if vehicle.status == "Reservado" and destination == "Disponível":
            return self.transition(vehicle=vehicle,new_status="Disponível",user_id=user_id,now=now,reason=reason,contract=contract,driver=driver)
        return self.transition(vehicle=vehicle,new_status=destination,user_id=user_id,now=now,reason=reason,contract=contract,driver=driver)
