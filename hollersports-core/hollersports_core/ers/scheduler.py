from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Dict, List


@dataclass(frozen=True)
class Step:
    name: str
    fn: Callable[[], None]
    depends_on: List[str]


class ERSScheduler:
    """
    Minimal deterministic scheduler: topological execution order.
    No concurrency to preserve determinism and economy.
    """

    def __init__(self) -> None:
        self._steps: Dict[str, Step] = {}

    def add(self, step: Step) -> None:
        if step.name in self._steps:
            raise ValueError(f"duplicate step: {step.name}")
        self._steps[step.name] = step

    def run(self) -> List[str]:
        executed: List[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def dfs(name: str) -> None:
            if name in visited:
                return
            if name in visiting:
                raise ValueError(f"cycle detected at {name}")
            visiting.add(name)
            step = self._steps[name]
            for dep in step.depends_on:
                if dep not in self._steps:
                    raise ValueError(f"missing dependency '{dep}' for step '{name}'")
                dfs(dep)
            step.fn()
            visiting.remove(name)
            visited.add(name)
            executed.append(name)

        for n in sorted(self._steps.keys()):
            dfs(n)
        return executed
