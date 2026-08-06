from arq.connections import RedisSettings

from app.core.config import get_settings


async def health_job(ctx: dict[str, object]) -> str:
    return "ok"


async def on_startup(ctx: dict[str, object]) -> None:
    return None


async def on_shutdown(ctx: dict[str, object]) -> None:
    return None


class WorkerSettings:
    functions = [health_job]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    on_startup = staticmethod(on_startup)
    on_shutdown = staticmethod(on_shutdown)
