# ChronosMesh Stage 5 — Disaster Recovery & Backup Runbook

## 1. Scope & Objective
This runbook defines backup, snapshotting, and restoration procedures for all persistent state and distributed infrastructure components in ChronosMesh:
1. **Neo4j Graph Database:** Event nodes, causal edges, metadata, and constraints.
2. **Apache Kafka Message Broker:** Event topics (`events.raw`, `events.causal`), partition logs, and consumer group offsets.
3. **Apache Flink State:** Tumbling window state, buffered out-of-order events, and watermark checkpoints.
4. **Application Configuration:** Secret management, JWT signing key rotations, and environment variables.

---

## 2. Component Backup Procedures

### 2.1 Neo4j Graph Database
Neo4j stores all reconstructed causal DAGs, anomaly detections, and TrueTime confidence scores.

#### Daily Offline/Online Backup (Enterprise/Community CLI):
```bash
# 1. Stop write traffic or coordinate a consistent snapshot
docker exec -it chronosmesh-neo4j neo4j-admin database dump neo4j --to-path=/data/dumps

# 2. Extract dump archive to external object storage (e.g., S3/GCS)
docker cp chronosmesh-neo4j:/data/dumps/neo4j.dump ./backups/neo4j_$(date +%Y%m%d_%H%M%S).dump
```

#### Verification & Consistency Check:
```bash
# Verify schema and integrity of backup
neo4j-admin database check neo4j
```

---

### 2.2 Apache Kafka Message Broker
Kafka holds volatile streaming events prior to stream processing.

#### Retention Policy & Offset Preservation:
- Default topic retention is configured to 7 days (`log.retention.hours=168`).
- Kafka message volume is ephemeral by design, but offsets must be mirrored:
```bash
# Backup consumer group offsets
docker exec -it chronosmesh-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group chronosmesh-flink-group > ./backups/kafka_offsets_$(date +%Y%m%d).txt
```

---

### 2.3 Apache Flink Checkpoints & Savepoints
Flink manages bounded window state and buffered out-of-order events.

#### Triggering a Manual Savepoint:
```bash
# Trigger an externalized savepoint before maintenance
docker exec -it chronosmesh-flink-jobmanager flink savepoint \
  <JOB_ID> /tmp/flink-savepoints
```

---

## 3. Disaster Recovery & Restoration Procedures

### 3.1 Neo4j Restoration:
```bash
# 1. Stop Neo4j container
docker compose stop neo4j

# 2. Restore database from snapshot dump
docker exec -it chronosmesh-neo4j neo4j-admin database load neo4j --from-path=/data/dumps --overwrite-destination=true

# 3. Start Neo4j container and verify indexes
docker compose start neo4j
python -c "from chronosmesh.storage.neo4j_store import Neo4jStore; s = Neo4jStore(); print('Connected:', s.is_connected()); s.init_schema()"
```

### 3.2 Flink Job Recovery from Savepoint:
```bash
# Resume pipeline from savepoint
docker exec -it chronosmesh-flink-jobmanager flink run \
  -s /tmp/flink-savepoints/<SAVEPOINT_ID> \
  -c chronosmesh.stream.FlinkJob /opt/chronosmesh.jar
```

### 3.3 Zero-Data-Loss Fallback Mode:
If Neo4j or Kafka experiences total network partition:
1. `KafkaEventProducer` automatically falls back to `InMemoryEventProducer`.
2. `Neo4jStore` automatically falls back to in-memory graph cache.
3. The FastAPI service continues serving the dashboard and recording events without throwing 500 errors.
4. Once infrastructure recovers, connection retry mechanisms re-establish persistence automatically.

---

## 4. Recovery Time & Point Objectives (RTO / RPO)

| Subsystem | Target RTO (Recovery Time) | Target RPO (Data Loss Window) | Fallback Mechanism |
| :--- | :--- | :--- | :--- |
| **FastAPI Backend** | `< 10 seconds` | Zero (Stateless) | Container auto-restart |
| **Kafka Broker** | `< 2 minutes` | `< 100 ms` (Acks=all) | In-memory local fallback buffer |
| **Neo4j Graph Store**| `< 5 minutes` | `< 1 hour` (Daily dump) | In-memory dual-write mirror |
| **Flink Processing** | `< 30 seconds`| `< 500 ms` (Checkpoint) | Replay from Kafka offset |
