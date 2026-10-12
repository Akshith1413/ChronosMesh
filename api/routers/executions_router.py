"""Executions: ingest events, then read the reconstructed causal graph, anomalies and metrics."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from api.auth import ROLE_ANALYST, get_current_user, require_role
from api.services.execution_service import ExecutionService, get_service

router = APIRouter()


class CreateExecution(BaseModel):
    name: str = Field("live execution", max_length=80)


class IngestRequest(BaseModel):
    """A batch of events in the ChronosMesh event contract.

    Each event needs ``event_id``, ``service`` (or ``service_id``) and ``event_type``; supply
    ``vector_clock``, ``lamport_clock``, ``parent_event_ids`` and ``event_time`` (ISO-8601) for
    causal reconstruction. Re-sending an event id is safe (idempotent).
    """

    events: List[Dict[str, Any]] = Field(..., min_length=1, max_length=1000)

    model_config = {"json_schema_extra": {"example": {"events": [{
        "event_id": "evt-104", "service": "payment-service", "event_type": "PAYMENT_COMPLETED",
        "trace_id": "trace-abc", "span_id": "span-payment-02", "parent_event_ids": ["evt-102"],
        "lamport_clock": 7,
        "vector_clock": {"order-service": 2, "payment-service": 4, "inventory-service": 1},
        "event_time": "2026-10-09T11:00:02Z"}]}}}


@router.post("", status_code=201, summary="Create a live execution to ingest events into")
async def create_execution(body: CreateExecution, user: dict = Depends(require_role(ROLE_ANALYST)),
                           svc: ExecutionService = Depends(get_service)):
    return svc.create_execution(user, body.name)


@router.get("", summary="List my executions (live and sampled)")
async def list_executions(kind: Optional[str] = Query(None, pattern="^(live|experiment|sample)$"),
                          limit: int = Query(50, ge=1, le=200), user: dict = Depends(get_current_user),
                          svc: ExecutionService = Depends(get_service)):
    return {"executions": svc.list_records(user, kind=kind, limit=limit)}


@router.get("/{execution_id}", summary="Execution status and statistics")
async def get_execution(execution_id: str, user: dict = Depends(get_current_user),
                        svc: ExecutionService = Depends(get_service)):
    return svc.get_record(user, execution_id)


@router.post("/{execution_id}/events", summary="Ingest a batch of events (idempotent)")
async def ingest_events(execution_id: str, body: IngestRequest, user: dict = Depends(require_role(ROLE_ANALYST)),
                        svc: ExecutionService = Depends(get_service)):
    return svc.ingest(user, execution_id, body.events)


@router.get("/{execution_id}/events", summary="Events of the execution as received")
async def list_events(execution_id: str, limit: int = Query(500, ge=1, le=5000),
                      user: dict = Depends(get_current_user), svc: ExecutionService = Depends(get_service)):
    return svc.events(user, execution_id, limit)


@router.get("/{execution_id}/graph", summary="Reconstructed causal graph (nodes, edges, roots, leaves, unresolved)")
async def get_graph(execution_id: str, max_nodes: int = Query(2000, ge=10, le=20000),
                    user: dict = Depends(get_current_user), svc: ExecutionService = Depends(get_service)):
    return svc.graph(user, execution_id, max_nodes)


@router.get("/{execution_id}/anomalies", summary="Detected anomalies, filterable by type and severity")
async def get_anomalies(execution_id: str, type: Optional[List[str]] = Query(None),
                        severity: Optional[str] = Query(None, pattern="^(?i)(critical|warning|info)$"),
                        limit: int = Query(500, ge=1, le=5000), user: dict = Depends(get_current_user),
                        svc: ExecutionService = Depends(get_service)):
    return svc.anomalies(user, execution_id, types=type, severity=severity, limit=limit)


@router.get("/{execution_id}/metrics", summary="Reconstruction statistics for the execution")
async def get_metrics(execution_id: str, user: dict = Depends(get_current_user),
                      svc: ExecutionService = Depends(get_service)):
    return svc.execution_metrics(user, execution_id)


@router.get("/{execution_id}/truth", summary="Ground-truth causal edges (simulated executions only)")
async def get_truth(execution_id: str, user: dict = Depends(get_current_user),
                    svc: ExecutionService = Depends(get_service)):
    return svc.truth(user, execution_id)


@router.post("/{execution_id}/explore", summary="Load into the Trace Explorer (what-if, root cause, timeline…)")
async def explore(execution_id: str, user: dict = Depends(require_role(ROLE_ANALYST)),
                  svc: ExecutionService = Depends(get_service)):
    return svc.load_into_explorer(user, execution_id)
