"""Small helpers shared by the API, persistence and worker layers."""

from __future__ import annotations

import dataclasses
import json
import math
import time
from decimal import Decimal
from typing import Any


def to_jsonable(obj: Any) -> Any:
    """Recursively convert to strictly JSON-compliant data (NaN/inf -> None, Decimal -> number)."""
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in obj]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return to_jsonable(dataclasses.asdict(obj))
    if hasattr(obj, "to_dict"):
        return to_jsonable(obj.to_dict())
    return str(obj)


def dumps(obj: Any) -> str:
    return json.dumps(to_jsonable(obj), separators=(",", ":"))


def now_ms() -> int:
    return int(time.time() * 1000)


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
