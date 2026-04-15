from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Deque, Optional

from ..types import AnomalyAlert, LogEvent


def _parse_ts(ts: str) -> float:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return datetime.now(timezone.utc).timestamp()


@dataclass
class MonitoringAgent:
    cpu_high_threshold: int = 85
    failed_login_burst: int = 5
    failed_login_window_seconds: int = 20

    _failed_login_ts: Deque[float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._failed_login_ts is None:
            self._failed_login_ts = deque()

    def observe(self, event: LogEvent) -> Optional[AnomalyAlert]:
        # Overload: CPU threshold
        cpu = event.get("cpu")
        if isinstance(cpu, int) and cpu >= self.cpu_high_threshold:
            return {"status": "anomaly_detected", "type": "overload"}

        # Crash: explicit crash-like error
        if event.get("level") in ("ERROR", "ALERT") and event.get("event") == "error":
            msg = (event.get("message") or "").lower()
            if "crash" in msg or "segfault" in msg or "process down" in msg:
                return {"status": "anomaly_detected", "type": "crash"}

        # Intrusion: burst of failed logins in a time window
        if event.get("event") == "auth" and event.get("status") == "failed":
            ts = _parse_ts(event.get("ts", ""))
            self._failed_login_ts.append(ts)
            cutoff = ts - self.failed_login_window_seconds
            while self._failed_login_ts and self._failed_login_ts[0] < cutoff:
                self._failed_login_ts.popleft()
            if len(self._failed_login_ts) >= self.failed_login_burst:
                return {"status": "anomaly_detected", "type": "intrusion"}

        return None

