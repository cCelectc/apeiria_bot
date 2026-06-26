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
    username: str = "admin"
    password_hash: str = ""
    jwt_secret: str = ""
    token_expire_days: int = 7
    trusted_proxies: list[str] = []
    real_ip_header: str = ""


class LogConfig(BaseModel):
    file: str = "data/logs/apeiria.log"
    level: str = "INFO"
    rotation: str = "10 MB"
    retention: str = "7 days"
    stream_buffer: int = 500


class ApeiriaConfig(BaseModel):
    database: DatabaseConfig = DatabaseConfig()
    web: WebConfig = WebConfig()
    logging: LogConfig = LogConfig()


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
