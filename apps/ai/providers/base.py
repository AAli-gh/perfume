"""رابط مشترک ارائه‌دهندگان مدل زبانی؛ هر ارائه‌دهنده جدید فقط همین رابط را پیاده می‌کند."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class AIUnavailable(Exception):
    """هیچ ارائه‌دهنده‌ای پیکربندی نشده یا سرویس در دسترس نیست."""


@dataclass
class AIRequest:
    instructions: str
    input: str
    max_tokens: int = 1024
    metadata: dict = field(default_factory=dict)


@dataclass
class AIResponse:
    text: str
    provider: str
    raw: dict = field(default_factory=dict)


class AIProvider(ABC):
    code: str = ""

    @abstractmethod
    def generate(self, request: AIRequest) -> AIResponse:
        """تولید متن برای یک درخواست."""


class NullProvider(AIProvider):
    """ارائه‌دهنده پیش‌فرض وقتی AI غیرفعال است."""

    code = "null"

    def generate(self, request: AIRequest) -> AIResponse:
        raise AIUnavailable("لایه هوش مصنوعی پیکربندی نشده است (AI_PROVIDER).")
