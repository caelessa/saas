import os
from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


class StorageNotFoundError(FileNotFoundError):
    """Arquivo não encontrado no armazenamento configurado."""


class StorageService:
    """Armazena arquivos no Cloudflare R2 e usa disco local apenas em desenvolvimento.

    Variáveis necessárias em produção:
      R2_ACCOUNT_ID
      R2_ACCESS_KEY_ID
      R2_SECRET_ACCESS_KEY
      R2_BUCKET_NAME

    R2_ENDPOINT_URL é opcional. Quando ausente, é montada a partir de R2_ACCOUNT_ID.
    """

    def __init__(self, local_root: Path):
        self.local_root = Path(local_root)
        self.local_root.mkdir(parents=True, exist_ok=True)

        self.account_id = os.getenv("R2_ACCOUNT_ID", "").strip()
        self.access_key_id = os.getenv("R2_ACCESS_KEY_ID", "").strip()
        self.secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
        self.bucket_name = os.getenv("R2_BUCKET_NAME", "frota-facil").strip() or "frota-facil"
        self.endpoint_url = os.getenv("R2_ENDPOINT_URL", "").strip()
        if not self.endpoint_url and self.account_id:
            self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"

        configured = all(
            [self.endpoint_url, self.access_key_id, self.secret_access_key, self.bucket_name]
        )
        self._client = None

        if configured:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name="auto",
                config=Config(signature_version="s3v4"),
            )

    @property
    def using_r2(self) -> bool:
        return self._client is not None

    @property
    def backend_name(self) -> str:
        return "Cloudflare R2" if self.using_r2 else "armazenamento local (temporário)"

    @staticmethod
    def _normalize_key(storage_key: str) -> str:
        return storage_key.replace("\\", "/").lstrip("/")

    def upload(self, stream: BinaryIO, storage_key: str, content_type: str | None = None) -> str:
        storage_key = self._normalize_key(storage_key)
        try:
            stream.seek(0)
        except (AttributeError, OSError):
            pass

        if self.using_r2:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type
            self._client.upload_fileobj(
                stream,
                self.bucket_name,
                storage_key,
                ExtraArgs=extra_args or None,
            )
        else:
            destination = self.local_root / storage_key
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as output:
                while True:
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
        return storage_key

    def download(self, storage_key: str) -> bytes:
        storage_key = self._normalize_key(storage_key)
        if self.using_r2:
            try:
                response = self._client.get_object(Bucket=self.bucket_name, Key=storage_key)
                return response["Body"].read()
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code in {"NoSuchKey", "404", "NotFound"}:
                    raise StorageNotFoundError(storage_key) from exc
                raise

        path = self.local_root / storage_key
        if not path.exists():
            raise StorageNotFoundError(storage_key)
        return path.read_bytes()

    def delete(self, storage_key: str) -> None:
        if not storage_key:
            return
        storage_key = self._normalize_key(storage_key)
        if self.using_r2:
            # A operação é idempotente: excluir uma chave inexistente não gera erro no S3/R2.
            self._client.delete_object(Bucket=self.bucket_name, Key=storage_key)
        else:
            path = self.local_root / storage_key
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


    def exists(self, storage_key: str) -> bool:
        """Informa se uma chave existe sem baixar o arquivo inteiro."""
        if not storage_key:
            return False
        storage_key = self._normalize_key(storage_key)
        if self.using_r2:
            try:
                self._client.head_object(Bucket=self.bucket_name, Key=storage_key)
                return True
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code in {"NoSuchKey", "404", "NotFound"}:
                    return False
                raise
        return (self.local_root / storage_key).exists()

    def tenant_usage(self, tenant_id: int) -> dict:
        """Conta objetos e bytes sob o prefixo da locadora."""
        prefix = f"{tenant_id}/"
        if self.using_r2:
            count = 0
            total_bytes = 0
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                for obj in page.get("Contents", []):
                    count += 1
                    total_bytes += int(obj.get("Size", 0))
            return {"objects": count, "bytes": total_bytes}

        base = self.local_root / str(tenant_id)
        if not base.exists():
            return {"objects": 0, "bytes": 0}
        files = [p for p in base.rglob("*") if p.is_file()]
        return {"objects": len(files), "bytes": sum(p.stat().st_size for p in files)}

    def check_connection(self) -> bool:
        """Valida credenciais e acesso ao bucket sem criar ou apagar objetos."""
        if not self.using_r2:
            return False
        self._client.head_bucket(Bucket=self.bucket_name)
        return True
