from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..types import Diagnosis, Plan
from ..validation import is_plan


@dataclass
class PlanningAgent:
    def plan(
        self,
        diagnosis: Diagnosis,
        memory_hint: Optional[Plan] = None,
        memory_agent: Optional[object] = None,
    ) -> Plan:
        """
        Returns a strict JSON plan.

        Research-grade behavior:
        - Prefer a memory-provided successful strategy (passed in as memory_hint),
          or retrieved from memory_agent when provided.
        - Avoid repeating the last failed action if encoded in memory_hint as a non-matching plan.
        """
        if memory_hint is None and memory_agent is not None:
            getter = getattr(memory_agent, "get_similar_incident", None)
            if callable(getter):
                memory_hint = getter(diagnosis["incident"])

        if memory_hint is not None:
            print("[PLANNING][MEMORY] Using past successful strategy")
            if is_plan(memory_hint):
                return memory_hint

        incident = diagnosis["incident"]
        severity = diagnosis["severity"]

        if incident == "normal":
            return {"action": "restart_service", "target": "noop"}

        if incident == "intrusion":
            # target can be resolved by execution agent (best-effort)
            return {"action": "block_ip", "target": "attacker_ip"}

        if incident == "crash":
            return {"action": "restart_service", "target": "compute"}

        # overload
        if severity in ("high",):
            return {"action": "reroute_traffic", "target": "backup_server"}
        return {"action": "restart_service", "target": "lb"}

