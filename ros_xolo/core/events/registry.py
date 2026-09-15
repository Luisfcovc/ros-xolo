from collections import defaultdict

_handlers = defaultdict(list)


def register(event_type, handler):
    _handlers[event_type].append(handler)
    return handler


def dispatch(event):
    for handler in _handlers[event.type]:
        handler(event)
