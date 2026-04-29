"""Handler registry for notification retry actions.

A handler is a callable `fn(notification) -> bool` that attempts to recover
from the underlying issue. Returning True means recovery succeeded and the
notification should be marked resolved; False means it failed again.
"""
import logging
from typing import Callable, Dict

logger = logging.getLogger(__name__)

_handlers: Dict[str, Callable] = {}


def register_handler(kind: str):
    def decorator(fn):
        _handlers[kind] = fn
        return fn

    return decorator


def get_handler(kind: str):
    return _handlers.get(kind)


def has_handler(kind: str) -> bool:
    return kind in _handlers
