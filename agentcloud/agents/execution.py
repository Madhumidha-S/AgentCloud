from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..simulator import SimState
from ..types import ExecutionResult, LogEvent, Plan


@dataclass
class ExecutionAgent:
    state: SimState = field(default_factory=SimState)
    demo_fail_first_reroute: bool = False
    _reroute_attempts: int = 0

    def execute(self, plan: Plan, recent_events: list[LogEvent]) -> ExecutionResult:
        action = plan["action"]
        target = plan["target"]

        if action == "restart_service":
            return self.restart_service(target)
        if action == "isolate_server":
            return self.isolate_server(target)
        if action == "reroute_traffic":
            return self.reroute_traffic(target)
        if action == "block_ip":
            return self.block_ip(target, recent_events)

        return ExecutionResult(
            success=False,
            details=f"Unknown action: {action}",
            new_state=self._state_dict(),
        )

    def restart_service(self, service: str) -> ExecutionResult:
        # In this simulated environment, restart toggles health back on.
        if service == "compute":
            self.state.primary_healthy = True
        return ExecutionResult(True, f"Restarted service '{service}'", self._state_dict())

    def isolate_server(self, server: str) -> ExecutionResult:
        self.state.isolated = True
        return ExecutionResult(True, f"Isolated server '{server}'", self._state_dict())

    def reroute_traffic(self, target: str) -> ExecutionResult:
        if target != "backup_server":
            return ExecutionResult(False, f"Unknown reroute target '{target}'", self._state_dict())
        self._reroute_attempts += 1
        if self.demo_fail_first_reroute and self._reroute_attempts == 1:
            return ExecutionResult(False, "Simulated reroute failure (demo)", self._state_dict())
        if not self.state.backup_healthy:
            return ExecutionResult(False, "Backup server unhealthy; cannot reroute", self._state_dict())
        self.state.active_server = "backup"
        return ExecutionResult(True, "Rerouted traffic to backup server", self._state_dict())

    def block_ip(self, target: str, recent_events: list[LogEvent]) -> ExecutionResult:
        ip = None
        if target != "attacker_ip":
            ip = target
        else:
            for e in reversed(recent_events[-50:]):
                if e.get("event") == "auth" and e.get("status") == "failed" and e.get("ip"):
                    ip = str(e.get("ip"))
                    break
        if not ip:
            return ExecutionResult(False, "Could not resolve attacker IP", self._state_dict())
        self.state.blocked_ips.add(ip)
        return ExecutionResult(True, f"Blocked IP {ip}", self._state_dict())

    def _state_dict(self) -> dict[str, Any]:
        return {
            "active_server": self.state.active_server,
            "primary_healthy": self.state.primary_healthy,
            "backup_healthy": self.state.backup_healthy,
            "isolated": self.state.isolated,
            "blocked_ips": sorted(self.state.blocked_ips),
        }

