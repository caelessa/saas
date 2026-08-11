from datetime import datetime, date
from zoneinfo import ZoneInfo


LEVEL_RANK = {'danger': 3, 'warning': 2, 'info': 1, 'success': 0}


def _parse_date(value):
    if not value:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(str(value), fmt).date()
        except (ValueError, TypeError):
            pass
    return None


def _fmt_km(value):
    try:
        return f'{int(value):,}'.replace(',', '.')
    except Exception:
        return str(value or 0)


def _upsert_alert(session, Alert, tenant_id, source_key, *, titulo, mensagem, nivel,
                  entidade=None, entidade_id=None, action_url=None, now=None):
    now = now or datetime.utcnow()
    alert = Alert.query.filter_by(tenant_id=tenant_id, source_key=source_key).first()
    if alert is None:
        alert = Alert(
            tenant_id=tenant_id,
            source_key=source_key,
            titulo=titulo,
            mensagem=mensagem,
            nivel=nivel,
            entidade=entidade,
            entidade_id=entidade_id,
            action_url=action_url,
            lido=False,
            criado_em=now,
            atualizado_em=now,
            resolvido_em=None,
        )
        session.add(alert)
        return alert

    changed = (
        alert.titulo != titulo or alert.mensagem != mensagem or alert.nivel != nivel or
        alert.entidade != entidade or alert.entidade_id != entidade_id or
        alert.action_url != action_url or alert.resolvido_em is not None
    )
    alert.titulo = titulo
    alert.mensagem = mensagem
    alert.nivel = nivel
    alert.entidade = entidade
    alert.entidade_id = entidade_id
    alert.action_url = action_url
    alert.resolvido_em = None
    alert.atualizado_em = now
    if changed:
        alert.lido = False
    return alert


def _resolve_missing(session, Alert, tenant_id, active_keys, prefixes, now=None):
    now = now or datetime.utcnow()
    q = Alert.query.filter(Alert.tenant_id == tenant_id, Alert.resolvido_em.is_(None))
    existing = q.all()
    for alert in existing:
        key = alert.source_key or ''
        if any(key.startswith(prefix) for prefix in prefixes) and key not in active_keys:
            alert.resolvido_em = now
            alert.atualizado_em = now
            alert.lido = True


def sync_operational_alerts(session, Alert, Maintenance, Vehicle, tenant_id,
                            maintenance_url='/manutencoes', vehicles_url='/veiculos'):
    """Recalcula alertas operacionais do tenant.

    A rotina é idempotente: atualiza alertas existentes em vez de duplicá-los e
    encerra automaticamente alertas cuja condição deixou de existir.
    """
    now = datetime.utcnow()
    today = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    active_keys = set()

    # Manutenções futuras por data e/ou quilometragem.
    maintenances = Maintenance.query.filter_by(tenant_id=tenant_id).all()
    for m in maintenances:
        vehicle = m.vehicle
        if not vehicle:
            continue
        plate = vehicle.placa or 'Veículo'
        service = m.tipo or 'Manutenção'
        warning_days = int(m.alerta_dias_antes if m.alerta_dias_antes is not None else 7)
        warning_km = int(m.alerta_km_antes if m.alerta_km_antes is not None else 500)

        due_date = _parse_date(m.proxima_data)
        if due_date:
            delta = (due_date - today).days
            key = f'maintenance:{m.id}:date'
            if delta < 0:
                active_keys.add(key)
                _upsert_alert(
                    session, Alert, tenant_id, key,
                    titulo=f'Manutenção vencida — {plate}',
                    mensagem=f'{service} venceu há {abs(delta)} dia(s), em {due_date.strftime("%d/%m/%Y")}.',
                    nivel='danger', entidade='Manutenção', entidade_id=m.id,
                    action_url=maintenance_url, now=now,
                )
            elif delta == 0:
                active_keys.add(key)
                _upsert_alert(
                    session, Alert, tenant_id, key,
                    titulo=f'Manutenção vence hoje — {plate}',
                    mensagem=f'{service} está programada para hoje ({due_date.strftime("%d/%m/%Y")}).',
                    nivel='danger', entidade='Manutenção', entidade_id=m.id,
                    action_url=maintenance_url, now=now,
                )
            elif delta <= warning_days:
                active_keys.add(key)
                _upsert_alert(
                    session, Alert, tenant_id, key,
                    titulo=f'Manutenção próxima — {plate}',
                    mensagem=f'{service} está programada para {due_date.strftime("%d/%m/%Y")} (faltam {delta} dia(s)).',
                    nivel='warning', entidade='Manutenção', entidade_id=m.id,
                    action_url=maintenance_url, now=now,
                )

        if m.proxima_km is not None:
            current_km = int(vehicle.km_atual or 0)
            due_km = int(m.proxima_km)
            remaining = due_km - current_km
            key = f'maintenance:{m.id}:km'
            if remaining < 0:
                active_keys.add(key)
                _upsert_alert(
                    session, Alert, tenant_id, key,
                    titulo=f'Manutenção por km vencida — {plate}',
                    mensagem=f'{service} ultrapassou em {_fmt_km(abs(remaining))} km a previsão de {_fmt_km(due_km)} km.',
                    nivel='danger', entidade='Manutenção', entidade_id=m.id,
                    action_url=maintenance_url, now=now,
                )
            elif remaining == 0:
                active_keys.add(key)
                _upsert_alert(
                    session, Alert, tenant_id, key,
                    titulo=f'Manutenção atingiu a quilometragem — {plate}',
                    mensagem=f'{service} atingiu a previsão de {_fmt_km(due_km)} km.',
                    nivel='danger', entidade='Manutenção', entidade_id=m.id,
                    action_url=maintenance_url, now=now,
                )
            elif remaining <= warning_km:
                active_keys.add(key)
                _upsert_alert(
                    session, Alert, tenant_id, key,
                    titulo=f'Manutenção por km próxima — {plate}',
                    mensagem=f'Faltam {_fmt_km(remaining)} km para {service} (prevista em {_fmt_km(due_km)} km).',
                    nivel='warning', entidade='Manutenção', entidade_id=m.id,
                    action_url=maintenance_url, now=now,
                )

    # Troca de óleo configurada diretamente no veículo.
    vehicles = Vehicle.query.filter_by(tenant_id=tenant_id).all()
    for v in vehicles:
        if not v.controlar_oleo or v.ultima_troca_oleo_km is None or not v.intervalo_oleo_km:
            continue
        next_km = int(v.ultima_troca_oleo_km) + int(v.intervalo_oleo_km)
        remaining = next_km - int(v.km_atual or 0)
        warning_km = int(v.alerta_oleo_km if v.alerta_oleo_km is not None else 100)
        key = f'oil:{v.id}'
        if remaining < 0:
            active_keys.add(key)
            _upsert_alert(
                session, Alert, tenant_id, key,
                titulo=f'Troca de óleo vencida — {v.placa}',
                mensagem=f'A troca de óleo está vencida há {_fmt_km(abs(remaining))} km. Próxima troca prevista em {_fmt_km(next_km)} km.',
                nivel='danger', entidade='Veículo', entidade_id=v.id,
                action_url=vehicles_url, now=now,
            )
        elif remaining <= warning_km:
            active_keys.add(key)
            _upsert_alert(
                session, Alert, tenant_id, key,
                titulo=f'Troca de óleo próxima — {v.placa}',
                mensagem=f'Faltam {_fmt_km(remaining)} km para a troca de óleo prevista em {_fmt_km(next_km)} km.',
                nivel='warning', entidade='Veículo', entidade_id=v.id,
                action_url=vehicles_url, now=now,
            )

    _resolve_missing(session, Alert, tenant_id, active_keys, ('maintenance:', 'oil:'), now=now)
    session.commit()
    return Alert.query.filter(
        Alert.tenant_id == tenant_id,
        Alert.resolvido_em.is_(None),
    ).order_by(Alert.criado_em.desc()).all()


def maintenance_indicator(m):
    """Retorna o pior estado entre prazo por data e por km para exibição."""
    today = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    vehicle = m.vehicle
    states = []
    details = []
    warning_days = int(m.alerta_dias_antes if m.alerta_dias_antes is not None else 7)
    warning_km = int(m.alerta_km_antes if m.alerta_km_antes is not None else 500)

    due_date = _parse_date(m.proxima_data)
    if due_date:
        delta = (due_date - today).days
        if delta < 0:
            states.append('danger'); details.append(f'Data vencida há {abs(delta)} dia(s)')
        elif delta == 0:
            states.append('danger'); details.append('Vence hoje')
        elif delta <= warning_days:
            states.append('warning'); details.append(f'Faltam {delta} dia(s)')
        else:
            states.append('ok'); details.append(f'Faltam {delta} dia(s)')

    if m.proxima_km is not None and vehicle is not None:
        remaining = int(m.proxima_km) - int(vehicle.km_atual or 0)
        if remaining < 0:
            states.append('danger'); details.append(f'KM vencida em {_fmt_km(abs(remaining))} km')
        elif remaining == 0:
            states.append('danger'); details.append('KM atingida')
        elif remaining <= warning_km:
            states.append('warning'); details.append(f'Faltam {_fmt_km(remaining)} km')
        else:
            states.append('ok'); details.append(f'Faltam {_fmt_km(remaining)} km')

    if not states:
        return {'state': 'off', 'label': 'Sem próxima previsão'}
    state = max(states, key=lambda s: {'danger': 3, 'warning': 2, 'ok': 1}.get(s, 0))
    labels = {'danger': 'Vencida', 'warning': 'Atenção', 'ok': 'Em dia'}
    return {'state': state, 'label': labels[state], 'detail': ' · '.join(details)}
