from contextvars import ContextVar
from threading import Lock
from typing import TYPE_CHECKING

from contexts.wrapper import RecyclableContextVar

if TYPE_CHECKING:
    from core.model_runtime.entities.model_entities import AIModelEntity
    from core.plugin.entities.plugin_daemon import PluginModelProviderEntity


"""
To avoid race-conditions caused by gunicorn thread recycling, using RecyclableContextVar to replace with
"""
plugin_model_providers: RecyclableContextVar[list["PluginModelProviderEntity"] | None] = RecyclableContextVar(
    ContextVar("plugin_model_providers")
)

plugin_model_providers_lock: RecyclableContextVar[Lock] = RecyclableContextVar(
    ContextVar("plugin_model_providers_lock")
)

plugin_model_schema_lock: RecyclableContextVar[Lock] = RecyclableContextVar(ContextVar("plugin_model_schema_lock"))

plugin_model_schemas: RecyclableContextVar[dict[str, "AIModelEntity"]] = RecyclableContextVar(
    ContextVar("plugin_model_schemas")
)
