"""OpenTelemetry instrumentation configuration."""

from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

from src.infrastructure.config import Settings
from src.infrastructure.telemetry.sanitizer import create_sanitizing_processor


def configure_opentelemetry(settings: Settings) -> None:
    """Configure OpenTelemetry instrumentation."""
    if not settings.otel_enabled:
        return

    # Create resource with service information
    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.app_env,
        }
    )

    # Configure tracing
    trace_provider = TracerProvider(
        resource=resource,
        sampler=ParentBasedTraceIdRatio(settings.otel_trace_sample_rate),
    )

    # Add sanitizing processor FIRST to sanitize attributes before export
    # This prevents sensitive data (auth headers, request bodies, DB queries)
    # from being sent to Jaeger/OTLP collectors
    trace_provider.add_span_processor(create_sanitizing_processor())

    # Add OTLP span exporter (runs after sanitization)
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        insecure=settings.otel_exporter_otlp_insecure,
    )
    trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

    # Set as global trace provider
    trace.set_tracer_provider(trace_provider)

    # Configure metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
            insecure=settings.otel_exporter_otlp_insecure,
        )
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Instrument logging to include trace context
    LoggingInstrumentor().instrument(set_logging_format=True)

    # Instrument HTTP clients for automatic trace propagation
    # This automatically adds W3C Trace Context headers to outgoing requests
    try:
        HTTPXClientInstrumentor().instrument()
    except Exception:
        # httpx may not be installed in all deployments
        pass

    try:
        RequestsInstrumentor().instrument()
    except Exception:
        # requests may not be installed in all deployments
        pass


def instrument_fastapi(app: Any) -> None:
    """Instrument FastAPI application with OpenTelemetry."""
    FastAPIInstrumentor.instrument_app(app)


def instrument_sqlalchemy(engine: Any) -> None:
    """Instrument SQLAlchemy engine with OpenTelemetry."""
    SQLAlchemyInstrumentor().instrument(
        engine=engine.sync_engine,
        enable_commenter=True,
        commenter_options={"db_framework": True, "opentelemetry_values": True},
    )


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer instance."""
    return trace.get_tracer(name)


def get_meter(name: str) -> metrics.Meter:
    """Get a meter instance."""
    return metrics.get_meter(name)
