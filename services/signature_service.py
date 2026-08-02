"""Validação e captura das evidências da assinatura eletrônica simples.

Este módulo cria uma trilha técnica de aceite. A adequação jurídica do fluxo e da
minuta deve ser revisada por profissional habilitado antes do uso comercial.
"""
import base64
import binascii
import re


class SignatureValidationError(ValueError):
    pass


class SignatureService:
    MAX_BYTES = 1_500_000

    def __init__(self, storage):
        self.storage = storage

    def validate_and_decode(self, data_uri: str) -> bytes:
        if not data_uri or not data_uri.startswith('data:image/png;base64,'):
            raise SignatureValidationError('Faça a assinatura no campo indicado.')
        payload = data_uri.split(',', 1)[1]
        try:
            content = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError):
            raise SignatureValidationError('A imagem da assinatura é inválida.')
        if not content.startswith(b'\x89PNG\r\n\x1a\n'):
            raise SignatureValidationError('A assinatura precisa estar no formato PNG.')
        if len(content) < 500:
            raise SignatureValidationError('A assinatura parece estar vazia. Assine novamente.')
        if len(content) > self.MAX_BYTES:
            raise SignatureValidationError('A assinatura excedeu o tamanho permitido.')
        return content

    def validate_identity(self, *, driver, nome: str, cpf: str, aceite: bool) -> None:
        if not aceite:
            raise SignatureValidationError('É necessário declarar que leu e concorda com o contrato.')
        if len(nome.strip()) < 5:
            raise SignatureValidationError('Informe o nome completo do signatário.')
        expected = re.sub(r'\D', '', driver.cpf or '')
        informed = re.sub(r'\D', '', cpf or '')
        if expected and informed != expected:
            raise SignatureValidationError('O CPF informado não corresponde ao motorista do contrato.')

    @staticmethod
    def client_ip(request) -> str:
        forwarded = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
        return forwarded or request.remote_addr or ''
