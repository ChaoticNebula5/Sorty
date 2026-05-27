from pathlib import PurePosixPath


def validate_object_key(object_key: str) -> PurePosixPath:
    if not object_key:
        raise ValueError("Object key must not be empty.")

    if "\\" in object_key:
        raise ValueError("Object keys must use forward slashes.")

    raw_parts = object_key.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError("Invalid object key.")

    key_path = PurePosixPath(object_key)
    if key_path.is_absolute():
        raise ValueError("Invalid object key.")

    return key_path
