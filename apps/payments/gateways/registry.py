_GATEWAYS = {}


def register(cls):
    _GATEWAYS[cls.code] = cls
    return cls


def get_gateway_class(code):
    try:
        return _GATEWAYS[code]
    except KeyError as exc:
        from .base import PaymentError

        raise PaymentError("درگاه پرداخت ناشناخته است.") from exc


def registered_codes():
    return sorted(_GATEWAYS)
