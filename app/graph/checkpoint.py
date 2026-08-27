from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver

from app.config import Settings


class CheckpointerHandle:
    """Owns optional RedisSaver context so its connection outlives the compiled graph."""

    def __init__(self, settings: Settings):
        self._context: AbstractContextManager | None = None
        self.saver: Any
        if settings.use_redis_checkpoint:
            try:
                from langgraph.checkpoint.redis import RedisSaver
            except ImportError as exc:
                raise RuntimeError(
                    "USE_REDIS_CHECKPOINT=true 需要安装 requirements-ai.txt"
                ) from exc
            self._context = RedisSaver.from_conn_string(settings.redis_url)
            self.saver = self._context.__enter__()
            self.saver.setup()
        else:
            self.saver = InMemorySaver()

    def close(self) -> None:
        if self._context is not None:
            self._context.__exit__(None, None, None)
