# ChronosMesh Event Schema

> **Source:** Direct inspection of `chronosmesh/events/event.py` and `chronosmesh/events/schemas.py`  
> **Author:** B. Guru Sai Prasad Reddy — Stage 2 Documentation

---

## Purpose

Every distributed event flowing through ChronosMesh carries this schema. It is the core unit of data that passes from mock microservices → Kafka → stream processor → causal engine → Neo4j → API → frontend. Getting this schema right and stable is the foundation of inter-component integration.

---

## Current Event Structure

The **canonical representation** in Stage 1 is a Python dataclass (`Event`) with a Pydantic mirror (`EventSchema`). Both live in `chronosmesh/events/`.

### Python Dataclass (`chronosmesh/events/event.py`)

```python
@dataclass
class EventMetadata:
    region: str = "unknown"                # Cloud region, e.g. "aws-mumbai", "gcp-singapore"
    availability_zone: str = "unknown"     # AZ within region
    clock_uncertainty_ms: float = 5.0      # Estimated clock skew bound (TrueTime-style)
    tags: Dict[str, str] = {}              # Arbitrary key-value tags

@dataclass
class Event:
    event_id: str           # UUID4 — globally unique
    service_id: str         # e.g. "order-svc", "payment-svc"
    event_type: str         # e.g. "ORDER_CREATED", "PAYMENT_STARTED"
    timestamp_ms: float     # Wall-clock epoch ms at event emission (subject to clock skew)
    lamport_ts: int         # Lamport logical clock counter at emission
    vector_clock: Dict[str, int]  # {service_id: counter} — full vector state
    hlc_ts: Optional[Dict[str, Any]]  # {"pt": float_epoch_s, "l": int_counter}
    trace_id: str           # UUID4 — links all events in one distributed transaction
    span_id: str            # 8-char hex — identifies this specific operation within trace
    parent_event_ids: List[str]  # Explicit causal parents declared by emitting service
    payload: Dict[str, Any]      # Application-specific data (order_id, amount, etc.)
    metadata: EventMetadata
    arrival_time_ms: float       # Epoch ms when ChronosMesh received this event (monotonic)
```

---

## Required Fields

| Field | Type | Nullable | Validation Rule |
|---|---|---|---|
| `event_id` | `str` (UUID4) | No | Must be non-empty, unique across all events |
| `service_id` | `str` | No | Must be non-empty |
| `event_type` | `str` | No | Must be non-empty |
| `timestamp_ms` | `float` | No | Must be > 0 |
| `lamport_ts` | `int` | No | Must be >= 0 |
| `trace_id` | `str` (UUID4) | No | Must be non-empty |
| `span_id` | `str` | No | Must be non-empty |
| `arrival_time_ms` | `float` | No | Must be > 0 |

---

## Optional Fields

| Field | Type | Default | Notes |
|---|---|---|---|
| `vector_clock` | `Dict[str, int]` | `{}` | Empty if service does not use vector clocks |
| `hlc_ts` | `Dict[str, Any]` | `None` | `{"pt": float, "l": int}` — only if HLC mode |
| `parent_event_ids` | `List[str]` | `[]` | Explicit causal links; empty = inferred-only |
| `payload` | `Dict[str, Any]` | `{}` | Application data; not used by causal engine |
| `metadata.availability_zone` | `str` | `"unknown"` | Informational only |
| `metadata.tags` | `Dict[str, str]` | `{}` | Custom labels |

---

## Clock Information

| Field | Format | Populated By | Used For |
|---|---|---|---|
| `lamport_ts` | `int` | `EventGenerator.emit_event()` increments per service | Fallback ordering when vector clock absent |
| `vector_clock` | `{service_id: int}` | `EventGenerator`: merged on send/receive | Primary causal ordering (HappensBefore) |
| `hlc_ts` | `{"pt": epoch_seconds, "l": int}` | `EventGenerator` HLC update logic | Alternative to pure logical clocks |
| `metadata.clock_uncertainty_ms` | `float` ms | Set per-service in `ScenarioBuilder.configs` | TrueTime-style confidence scoring |

---

## Causal Information

| Field | How Used |
|---|---|
| `parent_event_ids` | DAGBuilder adds explicit edges for declared parents |
| `vector_clock` | `HappensBeforeDetector` compares via component-wise ≤ |
| `lamport_ts` | Fallback when vector clock is empty; tie-broken by `event_id` lexicographic order |

---

## Arrival Information

| Field | How Used |
|---|---|
| `arrival_time_ms` | Stored in `ChronosMeshStore.arrival_order` (separate from causal order) |
| `timestamp_ms` | Physical time of event; used for time inversion anomaly detection |

---

## Service Information

| Field | Examples | Source |
|---|---|---|
| `service_id` | `"order-svc"`, `"payment-svc"`, `"inventory-svc"`, `"shipping-svc"` | Declared in `ScenarioBuilder.configs` |
| `metadata.region` | `"aws-mumbai"`, `"gcp-singapore"` | Declared in `ScenarioBuilder.configs` |

---

## Example Event (JSON wire format — `event.to_dict()`)

```json
{
  "event_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "service_id": "order-svc",
  "event_type": "ORDER_CREATED",
  "timestamp_ms": 1727506800000.0,
  "lamport_ts": 1,
  "vector_clock": {
    "order-svc": 1,
    "payment-svc": 0,
    "inventory-svc": 0,
    "shipping-svc": 0
  },
  "hlc_ts": {
    "pt": 1727506800.0,
    "l": 0
  },
  "trace_id": "trace-uuid-here",
  "span_id": "a1b2c3d4",
  "parent_event_ids": [],
  "payload": {
    "order_id": "ORD-001",
    "customer_id": "CUST-42"
  },
  "metadata": {
    "region": "aws-mumbai",
    "availability_zone": "unknown",
    "clock_uncertainty_ms": 5.0,
    "tags": {}
  },
  "arrival_time_ms": 1727506800347.0
}
```

---

## Validation Rules

From `chronosmesh/events/schemas.py` (`EventSchema` — Pydantic v2):

1. `event_id` is required (no default in Pydantic model)
2. `service_id` is required
3. `event_type` is required
4. `timestamp_ms` is required
5. `lamport_ts` is required
6. `vector_clock` is required (can be empty dict)
7. `trace_id` is required
8. `span_id` is required
9. `arrival_time_ms` is required
10. `hlc_ts` is optional (can be `null`)
11. `metadata` defaults to `EventMetadataSchema()` if omitted

---

## Compatibility Notes

| Downstream System | Compatibility |
|---|---|
| **Kafka** | `serialize_event(event)` → `bytes` (JSON-encoded); `deserialize_event(bytes)` → `Event` object |
| **Neo4j** | `event.to_dict()` produces a flat dict suitable for Neo4j node properties (no nested objects except `metadata` dict) |
| **API response** | `store.get_dag_json()` flattens node properties; API consumers receive `region` and `clock_uncertainty_ms` directly (not nested under `metadata`) |
| **Frontend** | D3.js DAG viz consumes `{id, service_id, event_type, timestamp_ms, lamport_ts, vector_clock, region}` per node |
| **Flink/Kafka Streams** | Stream processor in `chronosmesh/stream/processor.py` accepts `Event` objects directly |


---

# Published event contract & formal causal rules (added 2026-10-12)

## Contract (`Event.to_spec_dict()` / `Event.from_spec_dict()`)

| Contract field | Internal field | Notes |
|---|---|---|
| `event_id` | `event_id` | Globally unique; the **idempotency key** |
| `execution_id` | `execution_id` | One business flow / experiment run; falls back to `trace_id` |
| `service` | `service_id` | Emitting service |
| `event_type` | `event_type` | |
| `trace_id`, `span_id` | same | OpenTelemetry-style identifiers |
| `parent_event_ids` | same | Declared direct causes |
| `lamport_clock` | `lamport_ts` | |
| `vector_clock` | `vector_clock` | `{service: counter}`; each service increments only its own entry |
| `event_time` (ISO-8601 UTC) | `timestamp_ms` | When it happened at the producer — **subject to clock skew** |
| `ingestion_time` (ISO-8601 UTC) | `arrival_time_ms` | When the platform received it — assigned by the platform |

`Event.from_dict` accepts both naming styles, so existing producers keep working.

## Causal rules the engine applies

Let `a` and `b` be events with vector clocks `V_a`, `V_b` and `s_a` the service of `a`.

1. **Happens-before:** `a → b  ⇔  V_a ≤ V_b componentwise and V_a ≠ V_b`. Equivalent test used by the engine: `V_b[s_a] ≥ V_a[s_a]`.
2. **Concurrency:** `a ∥ b  ⇔  ¬(a → b) ∧ ¬(b → a)`. Total-order approaches (arrival order, wall clock) cannot express this.
3. **Edges are covering relations:** the graph contains an edge `x → b` iff `x → b` and no known `y` has `x → y → b`
   (transitive reduction). For each service only the latest seen event can be a direct predecessor, giving
   `O(events × services)` candidates.
4. **Verified declarations:** a declared parent is accepted only if `V_parent ≤ V_child`; otherwise it is rejected and reported
   as `CAUSAL_VIOLATION` — no edge is created from contradicted metadata.
5. **Unresolved dependencies:** a declared parent that has not been observed is recorded (`UNRESOLVED_PARENT`), never
   invented; when it arrives later the link appears automatically (the result is independent of arrival order).
6. **Lost events:** if an event of service `s` was lost, an edge bridging the hole is created from clocks and flagged
   `inferred=true, via_gap=true`.
7. **Idempotence:** duplicate `event_id`s are ignored after the first delivery and counted (`DUPLICATE_EVENT`).
8. **Acyclicity:** the graph must be a DAG; an edge that would close a cycle is dropped and reported.
9. **Missing clocks:** events without a vector clock fall back to their declared parents (marked `verified=false`); Lamport
   time alone can order but cannot prove concurrency.

Wall-clock timestamps are never used to create edges — only to detect `TIME_INVERSION` and `CLOCK_DRIFT`.
