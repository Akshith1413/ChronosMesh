"""
ChronosMesh AWS Lambda Event Enrichment Handler.

Simulates a lightweight serverless stream processor (AWS Lambda / Cloud Function)
triggered by event ingestion to decorate events with multi-region latency bounds,
clock uncertainty metadata, and ingestion transit metrics before Kafka/Flink processing.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Geo-latency matrix between simulated cloud regions (in milliseconds)
REGION_TRANSIT_ESTIMATES_MS = {
    ("aws-mumbai", "aws-mumbai"): 1.5,
    ("aws-mumbai", "aws-singapore"): 38.0,
    ("aws-mumbai", "gcp-mumbai"): 4.2,
    ("aws-mumbai", "gcp-singapore"): 42.0,
    ("aws-singapore", "gcp-singapore"): 2.1,
    ("gcp-mumbai", "gcp-singapore"): 41.5,
}


def enrich_event_payload(raw_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Core enrichment logic applied by Lambda function to each incoming event.
    """
    enriched = dict(raw_record)
    now_ms = time.time() * 1000.0

    # Ensure arrival timestamp is recorded
    if "arrival_time_ms" not in enriched or enriched["arrival_time_ms"] <= 0:
        enriched["arrival_time_ms"] = now_ms

    # Calculate observed network transit delta
    timestamp_ms = enriched.get("timestamp_ms", now_ms)
    transit_delta_ms = max(0.0, enriched["arrival_time_ms"] - timestamp_ms)

    # Decorate metadata
    metadata = enriched.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    service_id = enriched.get("service_id", "unknown-service")
    region = metadata.get("region", "aws-mumbai")

    # Inferred clock uncertainty if missing
    if "clock_uncertainty_ms" not in metadata or metadata["clock_uncertainty_ms"] <= 0:
        metadata["clock_uncertainty_ms"] = 5.0

    tags = metadata.get("tags", {})
    tags["enriched_by"] = "lambda-enrichment-v1"
    tags["transit_latency_ms"] = f"{transit_delta_ms:.2f}"
    tags["ingest_az"] = metadata.get("availability_zone", "ap-south-1a")

    metadata["tags"] = tags
    enriched["metadata"] = metadata

    return enriched


def lambda_handler(event: Dict[str, Any], context: Optional[Any] = None) -> Dict[str, Any]:
    """
    Standard AWS Lambda entrypoint for MSK / Kinesis event triggers.
    
    Accepts:
        event: {'records': [raw_events]} or standard event payload
    Returns:
        JSON response with processed count and status.
    """
    records = []
    if "records" in event:
        # Kinesis or MSK batch format
        for rec in event["records"]:
            if isinstance(rec, dict) and "data" in rec:
                # Decodes base64/json if needed
                records.append(rec["data"])
            else:
                records.append(rec)
    elif "event_id" in event:
        records.append(event)
    else:
        records = [event]

    processed = []
    for raw in records:
        try:
            if isinstance(raw, str):
                raw_dict = json.loads(raw)
            else:
                raw_dict = raw
            enriched = enrich_event_payload(raw_dict)
            processed.append(enriched)
        except Exception as e:
            logger.error(f"[Lambda] Failed to enrich event: {e}")

    return {
        "statusCode": 200,
        "processed_count": len(processed),
        "enriched_records": processed,
    }
