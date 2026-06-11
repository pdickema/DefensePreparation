from __future__ import annotations

from dataclasses import dataclass, field


class ConversionUnavailable(RuntimeError):
    """Raised when an optional converter is not installed or not reachable."""


@dataclass
class ConversionResult:
    markdown: str
    tool: str
    fallback_used: bool = False
    warnings: list[str] = field(default_factory=list)
