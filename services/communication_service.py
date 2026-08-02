"""Camada única de comunicação do Frota Fácil.

Mantém o WhatsApp Web como fallback e deixa a aplicação pronta para a
WhatsApp Business Platform (Cloud API). O envio pela API só ocorre quando a
locadora habilita e fornece as credenciais em Integrações.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests


class CommunicationError(RuntimeError):
    pass


@dataclass
class CommunicationResult:
    provider: str
    status: str
    external_id: str | None = None
    redirect_url: str | None = None
    response_payload: dict[str, Any] | None = None


class CommunicationService:
    def __init__(self, *, timeout: int = 20):
        self.timeout = timeout

    @staticmethod
    def parse_config(integration) -> dict[str, Any]:
        if not integration or not integration.configuracao:
            return {}
        try:
            value = json.loads(integration.configuracao)
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    def send_whatsapp(self, *, phone: str, message: str, integration=None,
                      template_name: str | None = None,
                      template_language: str = "pt_BR",
                      template_parameters: list[str] | None = None) -> CommunicationResult:
        config = self.parse_config(integration)
        provider = (config.get("provider") or "web").lower()
        if provider == "business":
            return self._send_business(
                phone=phone,
                message=message,
                config=config,
                template_name=template_name,
                template_language=template_language,
                template_parameters=template_parameters or [],
            )
        return CommunicationResult(
            provider="whatsapp_web",
            status="PREPARADA",
            redirect_url=f"https://wa.me/{phone}?text={quote(message)}",
        )

    def _send_business(self, *, phone: str, message: str, config: dict[str, Any],
                       template_name: str | None, template_language: str,
                       template_parameters: list[str]) -> CommunicationResult:
        token = (config.get("access_token") or "").strip()
        phone_number_id = (config.get("phone_number_id") or "").strip()
        graph_version = (config.get("graph_version") or "v23.0").strip()
        if not token or not phone_number_id:
            raise CommunicationError(
                "WhatsApp Business Platform ainda não possui Access Token e Phone Number ID configurados."
            )

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": phone,
        }
        if template_name:
            payload.update({
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": template_language},
                    "components": [{
                        "type": "body",
                        "parameters": [{"type": "text", "text": str(v)} for v in template_parameters],
                    }] if template_parameters else [],
                },
            })
        else:
            # Texto livre é aceito apenas dentro da janela de atendimento da Meta.
            payload.update({"type": "text", "text": {"preview_url": True, "body": message}})

        response = requests.post(
            f"https://graph.facebook.com/{graph_version}/{phone_number_id}/messages",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        )
        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text[:2000]}
        if not response.ok:
            detail = body.get("error", {}).get("message") if isinstance(body, dict) else None
            raise CommunicationError(detail or f"Falha no WhatsApp Business Platform (HTTP {response.status_code}).")
        message_id = None
        if isinstance(body, dict) and body.get("messages"):
            message_id = body["messages"][0].get("id")
        return CommunicationResult(
            provider="whatsapp_business",
            status="ENVIADA",
            external_id=message_id,
            response_payload=body,
        )
