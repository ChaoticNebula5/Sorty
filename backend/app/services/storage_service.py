from pathlib import Path
from typing import Protocol


class StorageService(Protocol):
    def put_bytes(self, object_key: str, data: bytes, content_type: str) -> None:
        ...

    def put_file(self, object_key: str, file_path: str | Path, content_type: str) -> None:
        ...

    def get_bytes(self, object_key: str) -> bytes:
        ...

    def download_to_temp(self, object_key: str) -> Path:
        ...

    def delete_object(self, object_key: str) -> None:
        ...

    def presigned_get_url(
        self,
        object_key: str,
        expires_seconds: int | None = None,
    ) -> str:
        ...

    def object_exists(self, object_key: str) -> bool:
        ...
