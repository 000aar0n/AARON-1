"""Context-scoped private credentials for the official OpenJarvis cloud engine."""
from contextlib import contextmanager
from contextvars import ContextVar
from openai import OpenAI
from openjarvis.core.registry import EngineRegistry
from openjarvis.engine.cloud import CloudEngine

_KEY=ContextVar("jarvis_private_provider_key",default=None)

@EngineRegistry.register("personal_cloud")
class PersonalCloudEngine(CloudEngine):
    engine_id="personal_cloud"
    def _init_clients(self):
        key=_KEY.get()
        if not key:
            raise PermissionError("A private provider key is required")
        self._openai_client=OpenAI(api_key=key,base_url="https://api.openai.com/v1",
                                   max_retries=0,timeout=45.0)

@contextmanager
def key_scope(key):
    token=_KEY.set(key)
    try:
        yield
    finally:
        _KEY.reset(token)
