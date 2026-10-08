# ChronosMesh Neo4j Schema

> **Author:** B. Guru Sai Prasad Reddy — Stage 2 Documentation  
> **Finding:** Neo4j is **NOT currently implemented** in the repository. The in-memory `ChronosMeshStore` is the only persistence layer.  
> This document defines the target Neo4j schema for when Surya's data layer is integrated.

---

## Current Persistence State

| Layer | Status |
|---|---|
| In-memory (`api/store.py`) | ✅ Active — used for all current API responses |
| Neo4j | ❌ Not implemented — no connection code, no Cypher queries |
| PostgreSQL / TimescaleDB | ❌ Not implemented |

No `neo4j` Python driver is listed in `pyproject.toml` or `requirements.txt`.

---

## Target Node Labels

Based on the `Event` dataclass and DAG structure:

### `:Event` Node

Represents one distributed system event. Maps directly from `Event.to_dict()`.

```cypher
CREATE (:Event {
  event_id:             String,   // PRIMARY KEY — UUID4
  service_id:           String,   // "order-svc"
  event_type:           String,   // "ORDER_CREATED"
  timestamp_ms:         Float,    // wall-clock ms at emission
  arrival_time_ms:      Float,    // wall-clock ms at ChronosMesh receipt
  lamport_ts:           Integer,
  vector_clock:         String,   // JSON string (Neo4j has no native Map type for storage)
  hlc_pt:               Float,    // hlc_ts["pt"] — physical component
  hlc_l:                Integer,  // hlc_ts["l"] — logical counter
  trace_id:             String,
  span_id:              String,
  region:               String,   // from metadata.region
  availability_zone:    String,   // from metadata.availability_zone
  clock_uncertainty_ms: Float,    // from metadata.clock_uncertainty_ms
  payload:              String,   // JSON string of payload dict
  tags:                 String    // JSON string of metadata.tags
})
```

### `:Scenario` Node

Groups events belonging to one scenario run.

```cypher
CREATE (:Scenario {
  scenario_id:   String,   // e.g. "order_payment_flow"
  name:          String,
  description:   String,
  pattern:       String,   // "chain" | "fork" | "diamond"
  loaded_at:     DateTime
})
```

### `:Service` Node

Represents a microservice (deduped across runs).

```cypher
CREATE (:Service {
  service_id: String,   // "order-svc"
  region:     String
})
```

---

## Target Relationship Types

### `HAPPENS_BEFORE`

Directed causal edge: source event causally precedes target event.

```cypher
(:Event)-[:HAPPENS_BEFORE {
  explicit:         Boolean,  // True if declared via parent_event_ids
  confidence:       Float,    // From ConfidenceScorer (0.0–1.0)
  confidence_method: String,  // "explicit" | "vector_clock" | "physical_time"
  uncertainty_ms:   Float
}]->(:Event)
```

### `BELONGS_TO`

Links event to its scenario.

```cypher
(:Event)-[:BELONGS_TO]->(:Scenario)
```

### `EMITTED_BY`

Links event to its service.

```cypher
(:Event)-[:EMITTED_BY]->(:Service)
```

---

## Target Indexes and Constraints

```cypher
-- Primary key constraint
CREATE CONSTRAINT event_id_unique IF NOT EXISTS
  FOR (e:Event) REQUIRE e.event_id IS UNIQUE;

-- Lookup indexes
CREATE INDEX event_trace_id IF NOT EXISTS FOR (e:Event) ON (e.trace_id);
CREATE INDEX event_service_id IF NOT EXISTS FOR (e:Event) ON (e.service_id);
CREATE INDEX event_timestamp IF NOT EXISTS FOR (e:Event) ON (e.timestamp_ms);
CREATE INDEX event_lamport IF NOT EXISTS FOR (e:Event) ON (e.lamport_ts);
CREATE INDEX scenario_id_unique IF NOT EXISTS FOR (s:Scenario) ON (s.scenario_id);
```

---

## Target Cypher Queries

The `api/services/neo4j_service.py` will wrap these:

```cypher
-- Get single event
MATCH (e:Event {event_id: $event_id}) RETURN e

-- Get all events in a trace
MATCH (e:Event {trace_id: $trace_id}) RETURN e ORDER BY e.lamport_ts

-- Get full DAG for a scenario
MATCH (s:Scenario {scenario_id: $scenario_id})<-[:BELONGS_TO]-(e:Event)
OPTIONAL MATCH (e)-[r:HAPPENS_BEFORE]->(child:Event)
RETURN e, r, child

-- Get ancestors of an event
MATCH (e:Event {event_id: $event_id})<-[:HAPPENS_BEFORE*]-(ancestor:Event)
RETURN ancestor

-- Get descendants of an event
MATCH (e:Event {event_id: $event_id})-[:HAPPENS_BEFORE*]->(descendant:Event)
RETURN descendant

-- Get concurrent events (neither is ancestor of the other)
MATCH (e:Event {event_id: $event_id})
MATCH (other:Event)
WHERE NOT (e)-[:HAPPENS_BEFORE*]->(other)
  AND NOT (other)-[:HAPPENS_BEFORE*]->(e)
  AND e.event_id <> other.event_id
RETURN other
```

---

## Connection Configuration

Expected environment variables (see `.env.example`):

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<set in .env — never commit>
NEO4J_DATABASE=chronosmesh
```

Recommended Python driver: `neo4j>=5.0` (not yet in `pyproject.toml`).

---

## Integration Note

Until Surya's Neo4j layer is ready, `api/services/neo4j_service.py` is designed with a **fallback pattern**: if `NEO4J_URI` is not set, it transparently falls back to the in-memory `ChronosMeshStore`. This means the API and frontend continue working during development without a running Neo4j instance.
