_CARRIERS = {}


def register(cls):
    _CARRIERS[cls.code] = cls
    return cls


def get_carrier_class(code):
    from .manual import ManualCarrier

    return _CARRIERS.get(code, ManualCarrier)


def carrier_choices():
    return [(code, cls.label) for code, cls in sorted(_CARRIERS.items(), key=lambda item: item[1].label)]
