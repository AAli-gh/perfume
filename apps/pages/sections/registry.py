_TYPES = {}


def register(cls):
    instance = cls()
    _TYPES[instance.key] = instance
    return cls


def get(key):
    return _TYPES.get(key)


def all_types():
    return list(_TYPES.values())


def choices():
    return [(t.key, t.label) for t in _TYPES.values()]
