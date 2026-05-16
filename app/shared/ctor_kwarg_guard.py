"""Проверка kwargs до распаковки в конструкторы.

Ловит лишние имена до тяжёлой инициализации.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable


def assert_ctor_kwargs(
    fn: Callable[..., Any],
    kwargs: dict[str, Any],
    *,
    label: str,
) -> None:
    """TypeError, если в kwargs есть имена вне сигнатуры fn.

    Для callable с ``**kwargs`` проверка отключена.
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return
    if any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    ):
        return
    accepted: set[str] = set()
    for p in sig.parameters.values():
        if p.name == "self":
            continue
        if p.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            accepted.add(p.name)
    extra = set(kwargs) - accepted
    if extra:
        qname = getattr(fn, "__qualname__", repr(fn))
        extra_s = sorted(extra)
        allowed_s = sorted(accepted)
        raise TypeError(
            f"{label}: unexpected keyword argument(s) {extra_s} "
            f"for {qname}; allowed={allowed_s}",
        )
