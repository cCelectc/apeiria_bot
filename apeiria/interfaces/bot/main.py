from __future__ import annotations

import nonebot

from apeiria.infra.runtime.bootstrap import initialize_nonebot


def run() -> None:
    initialize_nonebot()
    nonebot.run()


if __name__ == "__main__":
    run()
