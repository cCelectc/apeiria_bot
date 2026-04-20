"""Asset helpers for WebChat."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass
class ChatAsset:
    asset_id: str
    content_type: str
    file_name: str | None = None
    local_path: Path | None = None
    remote_url: str | None = None
    managed_file: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AssetManager:
    def __init__(self) -> None:
        self._assets: dict[str, ChatAsset] = {}
        self._asset_dir = Path("data/web_ui/chat/assets")
        self._asset_dir.mkdir(parents=True, exist_ok=True)

    def get(self, asset_id: str) -> ChatAsset | None:
        return self._assets.get(asset_id)

    def register_path(
        self,
        path: str | Path,
        *,
        content_type: str = "image/png",
        file_name: str | None = None,
    ) -> ChatAsset:
        asset_id = uuid4().hex
        asset = ChatAsset(
            asset_id=asset_id,
            content_type=content_type,
            file_name=file_name,
            local_path=Path(path),
            managed_file=False,
        )
        self._assets[asset_id] = asset
        return asset

    def register_bytes(
        self,
        data: bytes,
        *,
        content_type: str = "image/png",
        suffix: str = ".png",
    ) -> ChatAsset:
        asset_id = uuid4().hex
        file_path = self._asset_dir / f"{asset_id}{suffix}"
        file_path.write_bytes(data)
        asset = ChatAsset(
            asset_id=asset_id,
            content_type=content_type,
            file_name=file_path.name,
            local_path=file_path,
            managed_file=True,
        )
        self._assets[asset_id] = asset
        return asset

    def retain(self, referenced_asset_ids: set[str]) -> None:
        stale_asset_ids = [
            asset_id
            for asset_id in self._assets
            if asset_id not in referenced_asset_ids
        ]
        for asset_id in stale_asset_ids:
            asset = self._assets.pop(asset_id, None)
            if not asset or not asset.managed_file or asset.local_path is None:
                continue
            with contextlib.suppress(OSError):
                asset.local_path.unlink()
