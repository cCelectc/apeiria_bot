from __future__ import annotations

from typing import TYPE_CHECKING

import nonebot
import pytest
from nonebot.matcher import matchers
from nonebug import App
from nonebug.provider import NoneBugProvider

if TYPE_CHECKING:
    from collections.abc import Generator


def pytest_configure(config: pytest.Config) -> None:
    del config
    nonebot.init(command_start={"/", "!"}, superusers=set())
    matchers.set_provider(NoneBugProvider)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(name="app")
def nonebug_app() -> Generator[App, None, None]:
    matchers.clear()
    yield App()
    matchers.clear()
