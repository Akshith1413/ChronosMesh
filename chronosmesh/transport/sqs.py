"""Amazon SQS transport: producers -> events queue -> worker.

Messages carry batches of events plus a monotonically increasing ``seq`` per stream, which lets the
consumer ignore redelivered messages (SQS is at-least-once and unordered).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import boto3

from chronosmesh.utils import dumps

logger = logging.getLogger(__name__)

MAX_MESSAGE_BYTES = 20_000       # target payload per message (SQS allows 256 KiB; keep batches small)
MAX_BATCH_BYTES = 240_000        # SendMessageBatch limit is 256 KiB for the whole batch
MAX_BATCH_ENTRIES = 10


@dataclass
class QueueMessage:
    body: Dict[str, Any]
    receipt_handle: str
    sent_timestamp_ms: Optional[int] = None
    receive_count: int = 1


class SqsTransport:
    def __init__(self, queue_url: str, region: Optional[str] = None, client=None) -> None:
        self.queue_url = queue_url
        self._sqs = client or boto3.client("sqs", region_name=region)

    # ── producing ────────────────────────────────────────────────────────────
    def chunk_events(self, events: List[Dict[str, Any]]) -> Iterable[List[Dict[str, Any]]]:
        chunk: List[Dict[str, Any]] = []
        size = 0
        for e in events:
            n = len(dumps(e))
            if chunk and size + n > MAX_MESSAGE_BYTES:
                yield chunk
                chunk, size = [], 0
            chunk.append(e)
            size += n
        if chunk:
            yield chunk

    def _send(self, entries: List[Dict[str, Any]]) -> None:
        if not entries:
            return
        resp = self._sqs.send_message_batch(QueueUrl=self.queue_url, Entries=entries)
        failed = resp.get("Failed", [])
        if failed:
            raise RuntimeError(f"SQS rejected {len(failed)} message(s): {failed[0].get('Message')}")

    def publish_events(self, stream_id: str, events: List[Dict[str, Any]], *, kind: str = "live",
                       start_seq: int = 0) -> int:
        """Publish ``events`` as one or more messages. Returns the next free sequence number."""
        seq = start_seq
        batch: List[Dict[str, Any]] = []
        batch_bytes = 0
        for chunk in self.chunk_events(events):
            body = dumps({"v": 1, "type": "events", "kind": kind, "stream_id": stream_id, "seq": seq, "events": chunk})
            if batch and (len(batch) >= MAX_BATCH_ENTRIES or batch_bytes + len(body) > MAX_BATCH_BYTES):
                self._send(batch)
                batch, batch_bytes = [], 0
            batch.append({"Id": str(seq), "MessageBody": body})
            batch_bytes += len(body)
            seq += 1
        self._send(batch)
        return seq

    def publish_end(self, stream_id: str, total_messages: int, *, kind: str = "experiment") -> None:
        body = dumps({"v": 1, "type": "end", "kind": kind, "stream_id": stream_id, "total_messages": total_messages})
        self._send([{"Id": "end", "MessageBody": body}])

    # ── consuming ────────────────────────────────────────────────────────────
    def receive(self, max_messages: int = 10, wait_seconds: int = 20, visibility_timeout: int = 120) -> List[QueueMessage]:
        resp = self._sqs.receive_message(
            QueueUrl=self.queue_url, MaxNumberOfMessages=min(10, max_messages), WaitTimeSeconds=wait_seconds,
            VisibilityTimeout=visibility_timeout, AttributeNames=["SentTimestamp", "ApproximateReceiveCount"])
        out = []
        for m in resp.get("Messages", []):
            attrs = m.get("Attributes", {})
            try:
                body = json.loads(m["Body"])
            except json.JSONDecodeError:
                body = {"type": "invalid", "raw": m["Body"][:200]}
            out.append(QueueMessage(body, m["ReceiptHandle"],
                                    int(attrs["SentTimestamp"]) if "SentTimestamp" in attrs else None,
                                    int(attrs.get("ApproximateReceiveCount", 1))))
        return out

    def delete(self, msg: QueueMessage) -> None:
        self._sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=msg.receipt_handle)

    def depth(self) -> Dict[str, int]:
        a = self._sqs.get_queue_attributes(
            QueueUrl=self.queue_url,
            AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible",
                            "ApproximateNumberOfMessagesDelayed"])["Attributes"]
        return {"visible": int(a.get("ApproximateNumberOfMessages", 0)),
                "in_flight": int(a.get("ApproximateNumberOfMessagesNotVisible", 0)),
                "delayed": int(a.get("ApproximateNumberOfMessagesDelayed", 0))}

    @property
    def queue_name(self) -> str:
        return self.queue_url.rstrip("/").rsplit("/", 1)[-1]
