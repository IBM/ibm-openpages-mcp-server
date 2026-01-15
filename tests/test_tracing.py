#!/usr/bin/env python3
"""Test script to verify OpenTelemetry tracing is working"""

import sys
import time
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Setup tracing
resource = Resource(attributes={SERVICE_NAME: "test-service"})
provider = TracerProvider(resource=resource)

# Add OTLP exporter
otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

# Add console exporter
console_exporter = ConsoleSpanExporter()
provider.add_span_processor(BatchSpanProcessor(console_exporter))

trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

print("Creating test span...")
with tracer.start_as_current_span("test-span") as span:
    span.set_attribute("test.attribute", "test-value")
    print("Span created, sleeping 2 seconds...")
    time.sleep(2)

print("Waiting for export...")
time.sleep(3)
print("Done! Check Jaeger UI for 'test-service'")