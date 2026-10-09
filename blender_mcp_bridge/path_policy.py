"""Execution-host path validation; native canonical containment remains addon-side."""

from __future__ import annotations

import ntpath
import posixpath
from typing import Any


class RuntimePathPolicy:
    """Lexical remote containment without consulting the provider's filesystem."""

    def __init__(self, platform: str, base: str, roots: list[str]) -> None:
        if platform not in {"Windows", "Linux", "Darwin"}:
            raise ValueError("remote runtime platform must be Windows, Linux or Darwin")
        self._windows = platform == "Windows"
        self._path = ntpath if self._windows else posixpath
        self.roots = [self._absolute(root) for root in roots]
        if not self.roots:
            raise ValueError("remote runtime requires explicit allow-roots")
        self.base = self._absolute(base)
        self._require_contained(self.base)

    def _validate(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip() or "\x00" in value:
            raise ValueError("runtime path must be a non-empty string without NUL")
        if not self._windows:
            return
        normalized = value.replace("/", "\\")
        if normalized.startswith(("\\\\?\\", "\\\\.\\")):
            raise ValueError("Windows device paths are refused")
        drive, tail = ntpath.splitdrive(normalized)
        if ":" in tail or (drive and not drive.startswith("\\\\") and len(drive) != 2):
            raise ValueError("Windows alternate streams and invalid drives are refused")
        if (drive and not tail.startswith("\\")) or (not drive and tail.startswith("\\")):
            raise ValueError("Windows drive-relative and rooted-relative paths are refused")
        if any(
            part.endswith((" ", ".")) and part not in {".", ".."}
            for part in tail.split("\\")
            if part
        ):
            raise ValueError("Windows trailing dots/spaces are ambiguous")

    def _absolute(self, value: str) -> str:
        self._validate(value)
        if not self._path.isabs(value):
            raise ValueError("runtime base and roots must be absolute")
        return self._path.normpath(value)

    def _require_contained(self, value: str) -> None:
        needle = self._path.normcase(value)
        for root in self.roots:
            try:
                if self._path.commonpath(
                    [needle, self._path.normcase(root)]
                ) == self._path.normcase(root):
                    return
            except ValueError:
                continue
        raise ValueError("path is outside the runtime allow-roots")

    def resolve(self, value: str) -> str:
        self._validate(value)
        absolute = value if self._path.isabs(value) else self._path.join(self.base, value)
        result = self._path.normpath(absolute)
        self._require_contained(result)
        return result

    def resolve_arguments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        for key in ("filepath", "image_path", "output_path", "output_dir"):
            value = arguments.get(key)
            if value:
                arguments[key] = self.resolve(value)
        return arguments
