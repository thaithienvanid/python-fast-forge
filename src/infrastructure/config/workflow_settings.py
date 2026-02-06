"""Workflow engine configuration for Temporal."""

from pydantic import Field
from pydantic_settings import BaseSettings


class WorkflowSettings(BaseSettings):
    """Temporal workflow engine configuration.

    Handles configuration for distributed workflow orchestration using Temporal.
    """

    temporal_host: str = Field(
        default="localhost:7233",
        alias="TEMPORAL_HOST",
        description="Temporal server host and port",
    )
    temporal_namespace: str = Field(
        default="default",
        alias="TEMPORAL_NAMESPACE",
        description="Temporal namespace for workflow isolation",
    )
    temporal_task_queue: str = Field(
        default="fastapi-tasks",
        alias="TEMPORAL_TASK_QUEUE",
        description="Task queue name for workflow tasks",
    )
