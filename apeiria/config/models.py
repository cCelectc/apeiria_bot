from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel


class NoneBotConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080
    command_start: list[str] = ["/"]
    command_sep: list[str] = ["."]
    superusers: list[str] = []
    nickname: list[str] = ["Bot"]
    locale: str = "zh_CN"
    log_level: str = "INFO"


class DatabaseConfig(BaseModel):
    path: str = "data/apeiria.db"


class WebConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080


class ApeiriaConfig(BaseModel):
    database: DatabaseConfig = DatabaseConfig()
    web: WebConfig = WebConfig()


class AppConfig(BaseModel):
    nonebot: NoneBotConfig = NoneBotConfig()
    plugins: dict[str, dict] = {}
    adapters: dict[str, dict] = {}
    apeiria: ApeiriaConfig = ApeiriaConfig()

    _nonebot_field_names: ClassVar[tuple[str, ...]] = (
        "host",
        "port",
        "command_start",
        "command_sep",
        "superusers",
        "nickname",
        "locale",
        "log_level",
    )
