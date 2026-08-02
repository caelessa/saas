"""Abstração de provedores de assinatura.

A assinatura local continua disponível para homologação. Clicksign e DocuSign
ficam configuráveis por locadora e prontos para receber a implementação das
chamadas reais sem espalhar dependências pelo app.py.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class SignatureProviderError(RuntimeError):
    pass


@dataclass
class SignatureProviderConfig:
    provider: str = "local"
    enabled: bool = False
    settings: dict[str, Any] | None = None


class SignatureProviderService:
    SUPPORTED = {"local", "clicksign", "docusign"}

    @classmethod
    def from_integration(cls, integration) -> SignatureProviderConfig:
        if not integration or not integration.configuracao:
            return SignatureProviderConfig()
        try:
            settings = json.loads(integration.configuracao)
        except (TypeError, ValueError):
            settings = {}
        provider = str(settings.get("provider") or "local").lower()
        if provider not in cls.SUPPORTED:
            provider = "local"
        return SignatureProviderConfig(
            provider=provider,
            enabled=bool(integration.ativo),
            settings=settings,
        )

    @staticmethod
    def readiness(config: SignatureProviderConfig) -> tuple[bool, str]:
        settings = config.settings or {}
        if config.provider == "local":
            return True, "Assinatura local disponível para homologação."
        if config.provider == "clicksign":
            missing = [name for name in ("api_token", "workspace_key") if not settings.get(name)]
            return (not missing, "Pronta para conexão." if not missing else "Faltam credenciais da Clicksign.")
        if config.provider == "docusign":
            missing = [name for name in ("account_id", "integration_key") if not settings.get(name)]
            return (not missing, "Pronta para conexão." if not missing else "Faltam credenciais da DocuSign.")
        return False, "Provedor não suportado."
