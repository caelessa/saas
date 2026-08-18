"""Provedores de assinatura eletrônica do Frota Fácil.

Clicksign usa API 3.0 (Envelope). A implementação foi desenhada para Sandbox e
Produção sem espalhar detalhes HTTP pelo app.py.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import requests


class SignatureProviderError(RuntimeError):
    pass


@dataclass
class SignatureProviderConfig:
    provider: str = "local"
    enabled: bool = False
    settings: dict[str, Any] | None = None


@dataclass
class ClicksignEnvelopeResult:
    envelope_id: str
    document_id: str
    signer_id: str
    status: str = "running"


class ClicksignClient:
    """Cliente mínimo da Clicksign API v3."""

    def __init__(self, token: str, environment: str = "sandbox", timeout: int = 30):
        token = (token or "").strip()
        if not token:
            raise SignatureProviderError("Informe o Access Token da Clicksign.")
        self.environment = (environment or "sandbox").lower()
        self.base_url = (
            "https://sandbox.clicksign.com/api/v3"
            if self.environment == "sandbox"
            else "https://app.clicksign.com/api/v3"
        )
        self.timeout = timeout
        self.headers = {
            "Authorization": token,
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
        }

    def _request(self, method: str, path: str, payload: dict | None = None, expected=(200, 201, 202)) -> dict:
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method, url, headers=self.headers, json=payload, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise SignatureProviderError(f"Falha de comunicação com a Clicksign: {exc}") from exc
        if response.status_code not in expected:
            detail = ""
            try:
                body = response.json()
                errors = body.get("errors") if isinstance(body, dict) else None
                if errors:
                    parts = []
                    for err in errors[:3]:
                        if isinstance(err, dict):
                            parts.append(str(err.get("detail") or err.get("title") or err))
                        else:
                            parts.append(str(err))
                    detail = "; ".join(parts)
                else:
                    detail = json.dumps(body, ensure_ascii=False)[:700]
            except Exception:
                detail = (response.text or "")[:700]
            raise SignatureProviderError(
                f"Clicksign retornou HTTP {response.status_code}. {detail or 'Sem detalhes adicionais.'}"
            )
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}

    @staticmethod
    def _id(body: dict, label: str) -> str:
        try:
            value = body["data"]["id"]
        except Exception as exc:
            raise SignatureProviderError(f"A Clicksign não retornou o ID de {label}.") from exc
        return str(value)

    def test_connection(self) -> tuple[bool, str]:
        body = self._request("GET", "/envelopes", expected=(200,))
        count = None
        if isinstance(body, dict):
            count = (body.get("meta") or {}).get("record_count")
        extra = f" ({count} envelope(s) encontrado(s))" if count is not None else ""
        return True, f"Conexão com Clicksign {self.environment} realizada com sucesso{extra}."

    def create_envelope(self, name: str) -> str:
        payload = {
            "data": {"type": "envelopes", "attributes": {"name": name}}
        }
        return self._id(self._request("POST", "/envelopes", payload, expected=(201,)), "envelope")

    def upload_pdf(self, envelope_id: str, filename: str, pdf_bytes: bytes) -> str:
        encoded = base64.b64encode(pdf_bytes).decode("ascii")
        payload = {
            "data": {
                "type": "documents",
                "attributes": {
                    "filename": filename,
                    "content_base64": f"data:application/pdf;base64,{encoded}",
                },
            }
        }
        body = self._request("POST", f"/envelopes/{envelope_id}/documents", payload, expected=(201,))
        return self._id(body, "documento")

    def create_signer(self, envelope_id: str, name: str, email: str, cpf: str | None = None) -> str:
        attributes: dict[str, Any] = {
            "name": name,
            "email": email,
            "communicate_events": {
                "document_signed": "email",
                "signature_request": "email",
                "signature_reminder": "email",
            },
        }
        cpf = (cpf or "").strip()
        if cpf:
            attributes["documentation"] = cpf
            attributes["has_documentation"] = True
        payload = {"data": {"type": "signers", "attributes": attributes}}
        body = self._request("POST", f"/envelopes/{envelope_id}/signers", payload, expected=(201,))
        return self._id(body, "signatário")

    def _requirement(self, envelope_id: str, document_id: str, signer_id: str, attributes: dict) -> str:
        payload = {
            "data": {
                "type": "requirements",
                "attributes": attributes,
                "relationships": {
                    "document": {"data": {"type": "documents", "id": document_id}},
                    "signer": {"data": {"type": "signers", "id": signer_id}},
                },
            }
        }
        body = self._request("POST", f"/envelopes/{envelope_id}/requirements", payload, expected=(201,))
        return self._id(body, "requisito")

    def create_default_requirements(self, envelope_id: str, document_id: str, signer_id: str) -> None:
        # Qualificação: o signatário concorda/assina o documento.
        self._requirement(
            envelope_id, document_id, signer_id,
            {"action": "agree", "role": "sign"},
        )
        # Evidência/autenticação por e-mail: simples e apropriada para o Sandbox.
        self._requirement(
            envelope_id, document_id, signer_id,
            {"action": "provide_evidence", "auth": "email"},
        )

    def activate(self, envelope_id: str) -> None:
        payload = {
            "data": {
                "id": envelope_id,
                "type": "envelopes",
                "attributes": {"status": "running"},
            }
        }
        self._request("PATCH", f"/envelopes/{envelope_id}", payload, expected=(200,))

    def notify(self, envelope_id: str) -> None:
        payload = {
            "data": {"type": "notifications", "attributes": {}}
        }
        self._request("POST", f"/envelopes/{envelope_id}/notifications", payload, expected=(200, 201, 202))

    def envelope_details(self, envelope_id: str) -> dict:
        return self._request("GET", f"/envelopes/{envelope_id}", expected=(200,))

    def create_signature_flow(self, *, envelope_name: str, filename: str, pdf_bytes: bytes,
                              signer_name: str, signer_email: str, signer_cpf: str | None = None) -> ClicksignEnvelopeResult:
        signer_email = (signer_email or "").strip()
        if not signer_email or "@" not in signer_email:
            raise SignatureProviderError("Informe um e-mail válido do signatário para o teste Clicksign.")
        envelope_id = self.create_envelope(envelope_name)
        document_id = self.upload_pdf(envelope_id, filename, pdf_bytes)
        signer_id = self.create_signer(envelope_id, signer_name, signer_email, signer_cpf)
        self.create_default_requirements(envelope_id, document_id, signer_id)
        self.activate(envelope_id)
        self.notify(envelope_id)
        return ClicksignEnvelopeResult(envelope_id, document_id, signer_id, "running")


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
            missing = [name for name in ("api_token",) if not settings.get(name)]
            env = settings.get("environment", "sandbox")
            return (not missing, f"Pronta para Clicksign {env}." if not missing else "Falta o Access Token da Clicksign.")
        if config.provider == "docusign":
            missing = [name for name in ("account_id", "integration_key") if not settings.get(name)]
            return (not missing, "Pronta para conexão." if not missing else "Faltam credenciais da DocuSign.")
        return False, "Provedor não suportado."

    @classmethod
    def clicksign_client(cls, integration) -> ClicksignClient:
        config = cls.from_integration(integration)
        if config.provider != "clicksign" or not config.enabled:
            raise SignatureProviderError("Selecione Clicksign como provedor ativo em Integrações.")
        settings = config.settings or {}
        return ClicksignClient(settings.get("api_token", ""), settings.get("environment", "sandbox"))
