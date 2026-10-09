"""Connection/collection scope, without changing the backend retrieval strategy."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from threading import RLock

_scope = ContextVar("runbook_retrieval_scope", default=None)


class LockedClient:
    """One embedded client can serve both parallel analyzer threads."""
    def __init__(self, client):
        self.client, self.lock = client, RLock()

    def __getattr__(self, name):
        value = getattr(self.client, name)
        if not callable(value):
            return value
        def call(*args, **kwargs):
            with self.lock:
                return value(*args, **kwargs)
        return call


@lru_cache(maxsize=4)
def client_for(location, embedded):
    from qdrant_client import QdrantClient
    return LockedClient(QdrantClient(path=location, force_disable_check_same_thread=True)
                        if embedded else QdrantClient(url=location))


def current_scope():
    return _scope.get()


@contextmanager
def retrieval_scope(location, embedded, collection):
    token = _scope.set((client_for(location, embedded), collection))
    try:
        yield
    finally:
        _scope.reset(token)
