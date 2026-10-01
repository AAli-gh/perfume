import pytest
from django.test import override_settings

from apps.ai.providers import AIRequest, AIUnavailable, NullProvider, get_provider


def test_disabled_by_default_returns_null_provider():
    assert isinstance(get_provider(), NullProvider)
    with pytest.raises(AIUnavailable):
        get_provider().generate(AIRequest(instructions="x", input="y"))


@override_settings(AI_PROVIDER="does-not-exist")
def test_unknown_provider_raises():
    with pytest.raises(AIUnavailable):
        get_provider()
