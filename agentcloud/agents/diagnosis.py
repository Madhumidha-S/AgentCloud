from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable, Optional

from ..llm import LLMClient, build_llm_from_env
from ..types import AnomalyAlert, Diagnosis, LogEvent
from ..validation import is_diagnosis


@dataclass
class DiagnosisAgent:
    """
    CPU-only baseline diagnosis agent.

    It produces deterministic, structured JSON and is meant to be swappable
    with an LLM-backed version later.
    """

    llm: Optional[LLMClient] = None
    verbose: bool = True

    def __post_init__(self) -> None:
        if self.llm is None:
            self.llm = build_llm_from_env()

    def _fallback(self, alert: AnomalyAlert, recent_events: list[LogEvent]) -> Diagnosis:
        incident = alert["type"]
        events = recent_events[-50:]

        if incident == "overload":
            max_cpu = 0
            for e in events:
                cpu = e.get("cpu")
                if isinstance(cpu, int):
                    max_cpu = max(max_cpu, cpu)
            cause = (
                "High CPU usage likely due to traffic spike or runaway process"
                if max_cpu >= 95
                else "Elevated CPU usage likely due to increased load"
            )
            severity = "high" if max_cpu >= 85 else "medium"
            return {"incident": "overload", "cause": cause, "severity": severity}

        if incident == "intrusion":
            ip = None
            for e in reversed(events):
                if e.get("event") == "auth" and e.get("status") == "failed" and e.get("ip"):
                    ip = e.get("ip")
                    break
            cause = "Repeated failed logins indicate possible brute-force attempt"
            if ip:
                cause = f"{cause} from {ip}"
            return {"incident": "intrusion", "cause": cause, "severity": "high"}

        # crash
        msg = None
        for e in reversed(events):
            if e.get("event") == "error":
                msg = e.get("message")
                break
        cause = msg or "Service crash detected in compute service"
        return {"incident": "crash", "cause": cause, "severity": "high"}

    def diagnose(self, alert: AnomalyAlert, recent_events: Iterable[LogEvent]) -> Diagnosis:
        events = list(recent_events)[-60:]

        # Prefer LLM if configured, but always validate + fallback.
        if self.llm is not None:
            prompt = self._build_prompt(alert=alert, recent_events=events)
            try:
                if self.verbose:
                    print("[DIAGNOSIS][LLM] calling model")
                raw = self.llm.complete(prompt)
                parsed = _extract_json_object(raw)
                if is_diagnosis(parsed):
                    return parsed
                raise ValueError("LLM returned invalid diagnosis JSON")
            except Exception as e:
                if self.verbose:
                    print(f"[DIAGNOSIS][FALLBACK] {e}")
                return self._fallback(alert, events)

        if self.verbose:
            print("[DIAGNOSIS][FALLBACK] LLM not configured")
        return self._fallback(alert, events)

    def _build_prompt(self, *, alert: AnomalyAlert, recent_events: list[LogEvent]) -> str:
        # Strong JSON-only prompt to enforce strict output.
        # Include minimal context to keep tokens low.
        context_events = [
            {k: v for k, v in e.items() if k in ("ts", "level", "service", "event", "message", "cpu", "ip", "status")}
            for e in recent_events[-25:]
        ]
        return (
            "You are diagnosing incidents in a simulated cloud environment.\n"
            "Return ONLY a single JSON object and nothing else.\n"
            "The JSON MUST match this schema exactly:\n"
            '{\n'
            '  "incident": "overload | crash | intrusion | normal",\n'
            '  "cause": "short explanation",\n'
            '  "severity": "low | medium | high"\n'
            '}\n'
            "Rules:\n"
            "- If evidence is insufficient, set incident to \"normal\" with low severity.\n"
            "- Keep cause under 15 words.\n"
            "- Do not add extra keys.\n\n"
            f"Anomaly alert: {json.dumps(alert)}\n"
            f"Recent logs (most recent last): {json.dumps(context_events)}\n"
        )


def _extract_json_object(text: str) -> dict:
    """
    Extract the first JSON object from a model response.
    Accepts responses wrapped in code fences or with leading/trailing text.
    """
    text = text.strip()
    # Fast path: pure JSON
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)

    # Remove common code fences
    if "```" in text:
        parts = text.split("```")
        # take largest chunk that contains braces
        candidates = [p for p in parts if "{" in p and "}" in p]
        if candidates:
            text = max(candidates, key=len).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in response")
    return json.loads(text[start : end + 1])

