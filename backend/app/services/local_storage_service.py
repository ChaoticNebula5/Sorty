import shutil
import tempfile
from pathlib import Path

from app.services.object_keys import validate_object_key


class LocalStorageService:
    def __init__(self, storage_root: str | Path) -> None:
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, object_key: str, data: bytes, content_type: str) -> None:
        path = self._resolve_object_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def put_file(self, object_key: str, file_path: str | Path, content_type: str) -> None:
        path = self._resolve_object_path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file_path, path)

    def get_bytes(self, object_key: str) -> bytes:
        return self._resolve_object_path(object_key).read_bytes()

    def download_to_temp(self, object_key: str) -> Path:
        source = self._resolve_object_path(object_key)
        suffix = source.suffix

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)

        shutil.copyfile(source, temp_path)
        return temp_path

    def delete_object(self, object_key: str) -> None:
        path = self._resolve_object_path(object_key)
        if path.exists():
            path.unlink()

    def presigned_get_url(
        self,
        object_key: str,
        expires_seconds: int | None = None,
    ) -> str:
        return self._resolve_object_path(object_key).as_uri()

    def object_exists(self, object_key: str) -> bool:
        return self._resolve_object_path(object_key).is_file()

    def _resolve_object_path(self, object_key: str) -> Path:
        key_path = validate_object_key(object_key)
        resolved = (self.storage_root / Path(*key_path.parts)).resolve()
        root = self.storage_root.resolve()

        if not resolved.is_relative_to(root):
            raise ValueError("Object key escapes storage root.")

        return resolved
