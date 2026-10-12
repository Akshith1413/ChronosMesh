"""Publish ChronosMesh application metrics to Amazon CloudWatch (namespace ``ChronosMesh``).

CloudWatch is the AWS-native monitoring layer: alarms and the Grafana CloudWatch data source read
these. Publishing never raises -- monitoring must not take the pipeline down.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CloudWatchPublisher:
    def __init__(self, namespace: str = "ChronosMesh", region: Optional[str] = None, client=None,
                 dimensions: Optional[Dict[str, str]] = None) -> None:
        self.namespace = namespace
        self._dimensions = [{"Name": k, "Value": v} for k, v in (dimensions or {}).items()]
        if client is not None:
            self._cw = client
        else:
            import boto3

            self._cw = boto3.client("cloudwatch", region_name=region)

    def put(self, metrics: Dict[str, Any], *, unit_overrides: Optional[Dict[str, str]] = None) -> bool:
        units = {"ReconstructionSeconds": "Seconds", "QueueOldestMessageAge": "Seconds"}
        units.update(unit_overrides or {})
        now = time.time()
        data: List[Dict[str, Any]] = []
        for name, value in metrics.items():
            if value is None:
                continue
            data.append({"MetricName": name, "Value": float(value), "Timestamp": now,
                         "Unit": units.get(name, "Count"), "Dimensions": self._dimensions})
        try:
            for i in range(0, len(data), 20):
                self._cw.put_metric_data(Namespace=self.namespace, MetricData=data[i:i + 20])
            return True
        except Exception as exc:
            logger.warning("CloudWatch put_metric_data failed: %s", exc)
            return False

    def queue_age_seconds(self, queue_name: str) -> Optional[float]:
        """ApproximateAgeOfOldestMessage as reported by SQS itself (last 5 minutes)."""
        try:
            now = time.time()
            resp = self._cw.get_metric_statistics(
                Namespace="AWS/SQS", MetricName="ApproximateAgeOfOldestMessage",
                Dimensions=[{"Name": "QueueName", "Value": queue_name}],
                StartTime=now - 300, EndTime=now + 60, Period=60, Statistics=["Maximum"])
            points = sorted(resp.get("Datapoints", []), key=lambda p: p["Timestamp"])
            return float(points[-1]["Maximum"]) if points else 0.0
        except Exception as exc:
            logger.debug("queue age lookup failed: %s", exc)
            return None

    def last_datapoint_age(self, metric: str, dimensions: Dict[str, str], *, window_s: int = 900) -> Optional[float]:
        """Seconds since this app metric last had a datapoint (None if there was none in the window)."""
        now = time.time()
        resp = self._cw.get_metric_statistics(
            Namespace=self.namespace, MetricName=metric,
            Dimensions=[{"Name": k, "Value": v} for k, v in dimensions.items()],
            StartTime=now - window_s, EndTime=now + 60, Period=60, Statistics=["Sum"])  # +60: query timestamps lose sub-second precision
        points = [p for p in resp.get("Datapoints", []) if p.get("Sum", 0) > 0]
        if not points:
            return None
        newest = max(p["Timestamp"] for p in points)
        return max(0.0, now - newest.timestamp())
