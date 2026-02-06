"""Observability configuration for telemetry and tracing."""

from pydantic import Field
from pydantic_settings import BaseSettings


class ObservabilitySettings(BaseSettings):
    """OpenTelemetry and observability configuration.

    Handles distributed tracing, metrics collection, and telemetry export.
    """

    otel_enabled: bool = Field(
        default=False,
        alias="OTEL_ENABLED",
        description="Enable OpenTelemetry instrumentation",
    )
    otel_service_name: str = Field(
        default="fastapi-boilerplate",
        alias="OTEL_SERVICE_NAME",
        description="Service name for OpenTelemetry traces",
    )
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4317",
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
        description="OTLP exporter endpoint (e.g., Jaeger, Tempo)",
    )
    otel_exporter_otlp_insecure: bool = Field(
        default=True,
        alias="OTEL_EXPORTER_OTLP_INSECURE",
        description="Use insecure connection to OTLP endpoint",
    )
    otel_trace_sample_rate: float = Field(
        default=1.0,
        alias="OTEL_TRACE_SAMPLE_RATE",
        description="Sampling rate for traces (0.0 to 1.0)",
    )
