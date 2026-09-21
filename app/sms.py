"""SMS provider abstraction.

Real providers (e.g. an SMS gateway) are configured per environment. Tests
and local development use the fake in-memory provider so no external
network call is ever made outside production.
"""

from abc import ABC, abstractmethod


class SmsProvider(ABC):
    @abstractmethod
    def send(self, phone_number: str, message: str) -> None: ...


class FakeSmsProvider(SmsProvider):
    """Records sent messages in memory instead of calling a real gateway."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, phone_number: str, message: str) -> None:
        self.sent.append((phone_number, message))


_provider: SmsProvider = FakeSmsProvider()


def get_sms_provider() -> SmsProvider:
    return _provider
