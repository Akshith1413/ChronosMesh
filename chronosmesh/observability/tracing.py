"""OpenTelemetry setup: traces from the API are exported over OTLP/HTTP to the Collector.

Disabled unless ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set (or ``OTEL_CONSOLE=true``), so local runs and
tests have zero overhead and no network dependency.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)
_configured = False


def configure_tracing(service_name: str = "chronosmesh-api", app: Optional[Any] = None) -> bool:
    """Install a tracer provider and (optionally) instrument a FastAPI app. Returns True if enabled."""
    global _configured
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    console = os.getenv("OTEL_CONSOLE", "").lower() in ("1", "true", "yes")
    if _configured or not (endpoint or console):
        return _configured
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        provider = TracerProvider(resource=Resource.create({
            "service.name": os.getenv("OTEL_SERVICE_NAME", service_name),
            "deployment.environment": os.getenv("ENVIRONMENT", "local"),
        }))
        if endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(
                endpoint=endpoint.rstrip("/") + "/v1/traces")))
        if console:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)
        if app is not None:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics,/api/health")
        _configured = True
        logger.info("OpenTelemetry tracing enabled (endpoint=%s)", endpoint or "console")
    except Exception as exc:  # observability must never stop the service
        logger.warning("OpenTelemetry setup failed: %s", exc)
    return _configured


def get_tracer(name: str = "chronosmesh"):
    from opentelemetry import trace

    return trace.get_tracer(name)
