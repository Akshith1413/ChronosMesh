"""Event transport (Amazon SQS now; Kafka/MSK is the documented upgrade path)."""

from chronosmesh.transport.sqs import QueueMessage, SqsTransport

__all__ = ["QueueMessage", "SqsTransport"]
