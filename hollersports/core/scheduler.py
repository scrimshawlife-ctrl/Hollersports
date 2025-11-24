"""
ERS (Event-Reactive Scheduler) pattern for composable job execution.

Jobs are small, focused units of work that:
- Have clear inputs and outputs
- Are deterministic given the same inputs
- Can be scheduled and orchestrated independently
- Track provenance and dependencies
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from hollersports.core.config import ProvenanceMetadata

# Type variables for generic job I/O
InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class JobStatus(str, Enum):
    """Status of a job execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobResult(Generic[OutputT]):
    """Result of a job execution."""

    job_id: str
    status: JobStatus
    output: OutputT | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    provenance: ProvenanceMetadata | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float | None:
        """Compute execution duration if both timestamps exist."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class Job(ABC, Generic[InputT, OutputT]):
    """
    Abstract base class for an ERS job.

    Jobs should be:
    - Small and focused (single responsibility)
    - Deterministic (same input → same output given same config)
    - Composable (outputs can feed into other jobs)
    - Traceable (full provenance)
    """

    def __init__(self, job_id: str, provenance: ProvenanceMetadata):
        """
        Initialize job.

        Args:
            job_id: Unique identifier for this job execution
            provenance: Provenance metadata for reproducibility
        """
        self.job_id = job_id
        self.provenance = provenance

    @abstractmethod
    def execute(self, input_data: InputT) -> OutputT:
        """
        Execute the job logic.

        Args:
            input_data: Typed input for this job

        Returns:
            Typed output from this job

        Raises:
            Exception: If job fails
        """
        pass

    def run(self, input_data: InputT) -> JobResult[OutputT]:
        """
        Run the job with full result tracking.

        Args:
            input_data: Input for the job

        Returns:
            JobResult with status, output, timing, and provenance
        """
        result = JobResult[OutputT](
            job_id=self.job_id,
            status=JobStatus.RUNNING,
            started_at=datetime.utcnow(),
            provenance=self.provenance,
        )

        try:
            output = self.execute(input_data)
            result.status = JobStatus.COMPLETED
            result.output = output
        except Exception as e:
            result.status = JobStatus.FAILED
            result.error = str(e)
        finally:
            result.completed_at = datetime.utcnow()

        return result

    @property
    def name(self) -> str:
        """Human-readable job name."""
        return self.__class__.__name__


class JobGraph:
    """
    Simple directed acyclic graph (DAG) for job orchestration.

    Allows scheduling dependent jobs in correct order.
    Future: expand to support parallel execution, retries, etc.
    """

    def __init__(self) -> None:
        """Initialize empty job graph."""
        self.jobs: dict[str, Job[Any, Any]] = {}
        self.dependencies: dict[str, list[str]] = {}

    def add_job(self, job: Job[Any, Any], depends_on: list[str] | None = None) -> None:
        """
        Add a job to the graph.

        Args:
            job: Job instance to add
            depends_on: List of job_ids this job depends on
        """
        self.jobs[job.job_id] = job
        self.dependencies[job.job_id] = depends_on or []

    def execute(self, start_job_id: str, initial_input: Any) -> dict[str, JobResult[Any]]:
        """
        Execute jobs starting from a given job.

        Args:
            start_job_id: ID of job to start execution from
            initial_input: Input for the starting job

        Returns:
            Dict mapping job_id -> JobResult for all executed jobs

        Note:
            This is a simple implementation. Production would use async execution,
            proper DAG traversal, and parallel execution where possible.
        """
        results: dict[str, JobResult[Any]] = {}

        # Simple single-job execution for now
        job = self.jobs[start_job_id]
        result = job.run(initial_input)
        results[start_job_id] = result

        return results
