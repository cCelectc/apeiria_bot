from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from apeiria.db.base import Base, ISOTimestampMixin


class MCPServer(ISOTimestampMixin, Base):
    __tablename__ = "mcp_servers"
    __table_args__ = (
        CheckConstraint(
            "transport IN ('stdio', 'sse')",
            name="ck_mcp_servers_transport",
        ),
        CheckConstraint("enabled IN (0, 1)", name="ck_mcp_servers_enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text)
    transport: Mapped[str] = mapped_column(Text)
    command: Mapped[str | None] = mapped_column(Text)
    args_json: Mapped[str | None] = mapped_column(Text)
    env_json: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    headers_json: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[int] = mapped_column(Integer, default=1)


class ACPAgent(ISOTimestampMixin, Base):
    __tablename__ = "acp_agents"
    __table_args__ = (
        CheckConstraint("enabled IN (0, 1)", name="ck_acp_agents_enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text)
    command: Mapped[str] = mapped_column(Text)
    args_json: Mapped[str | None] = mapped_column(Text)
    env_json: Mapped[str | None] = mapped_column(Text)
    workspace: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
