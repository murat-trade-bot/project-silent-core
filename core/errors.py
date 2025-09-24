from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


class ExecutionError(Exception): ...
class NetworkError(ExecutionError): ...
class ExchangeReject(ExecutionError): ...
class RuleViolation(ExecutionError): ...
class CooldownReject(ExecutionError): ...


@dataclass
class ClassifiedError:
    status: str
    message: str


def classify_exception(e: BaseException) -> ClassifiedError:
    # Bilinen özel sınıflar
    if isinstance(e, CooldownReject):
        return ClassifiedError("cooldown-reject", str(e))
    if isinstance(e, RuleViolation):
        return ClassifiedError("rule-violation", str(e))
    if isinstance(e, ExchangeReject):
        return ClassifiedError("exchange-reject", str(e))
    if isinstance(e, NetworkError) or isinstance(e, TimeoutError) or "timeout" in str(e).lower():
        return ClassifiedError("network-error", str(e))
    # Varsayılan
    return ClassifiedError("unknown-error", str(e))
