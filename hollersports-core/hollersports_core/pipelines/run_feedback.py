from __future__ import annotations
from ..ers.scheduler import ERSScheduler, Step
from ..feedback.cli import main as feedback_main


def run() -> list[str]:
    """
    Minimal ERS pipeline:
      1) validate inputs (implicit via pydantic in CLI)
      2) feedback update
      3) (future) emit downstream recalibration artifacts
    """
    sch = ERSScheduler()

    def _step_feedback() -> None:
        feedback_main()

    sch.add(Step(name="feedback_update", fn=_step_feedback, depends_on=[]))
    return sch.run()


if __name__ == "__main__":
    executed = run()
    print({"executed": executed})
