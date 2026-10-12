"""Experiments: configure a fault-injected simulation, run it, read the evaluation."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from api.auth import ROLE_ANALYST, get_current_user, require_role
from api.services.execution_service import ExecutionService, get_service
from chronosmesh.simulator.config import DELIVERY_MODES, LIMITS

router = APIRouter()


class ExperimentRequest(BaseModel):
    """Experiment parameters. Ranges follow the ChronosMesh blueprint (§9)."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field("experiment", max_length=80)
    num_services: int = Field(4, ge=LIMITS["num_services"][0], le=LIMITS["num_services"][1],
                              description="Simulated microservices (e.g. 4, 10, 25, 50)")
    num_events: int = Field(1000, ge=LIMITS["num_events"][0], le=LIMITS["num_events"][1])
    events_per_execution: int = Field(20, ge=LIMITS["events_per_execution"][0], le=LIMITS["events_per_execution"][1])
    network_delay_ms: float = Field(200.0, ge=0, le=2000, description="Maximum one-way delivery delay")
    duplicate_rate: float = Field(0.0, ge=0, le=0.10)
    missing_rate: float = Field(0.0, ge=0, le=0.05)
    clock_drift_ms: float = Field(0.0, ge=0, le=5000, description="Max per-service wall-clock offset")
    cross_region_delay_ms: float = Field(0.0, ge=0, le=2000, description="Extra delivery delay for services far from the ingestion region")
    metadata_loss_rate: float = Field(0.0, ge=0, le=1, description="Fraction of events that lose their vector clock")
    retry_rate: float = Field(0.0, ge=0, le=0.10, description="Fraction of events that trigger a retry storm")
    retry_burst: int = Field(6, ge=LIMITS["retry_burst"][0], le=LIMITS["retry_burst"][1], description="Retries per storm")
    delivery_mode: str = Field("randomized", description=f"One of {DELIVERY_MODES}")
    worker_failures: int = Field(0, ge=0, le=10, description="Simulated worker crash/restarts during processing")
    repeats: int = Field(1, ge=1, le=30)
    seed: int = Field(42, ge=0)
    transport: str = Field("direct", description="'direct' (in-process) or 'sqs' (publish to the queue; worker reconstructs)")
    branching: float = Field(0.7, ge=0, le=1)


@router.get("/options", summary="Allowed parameter ranges and defaults for the experiment form")
async def options(_: dict = Depends(get_current_user), svc: ExecutionService = Depends(get_service)):
    return {
        "limits": {k: list(v) for k, v in LIMITS.items()},
        "delivery_modes": list(DELIVERY_MODES),
        "transports": ["direct"] + (["sqs"] if svc.transport is not None else []),
        "max_experiment_events": svc.settings.max_experiment_events,
        "defaults": ExperimentRequest().model_dump(),
        "approaches": ["arrival_order", "wall_clock", "declared_only", "chronosmesh"],
    }


@router.post("", status_code=201, summary="Create an experiment (does not start it)")
async def create_experiment(body: ExperimentRequest, user: dict = Depends(require_role(ROLE_ANALYST)),
                            svc: ExecutionService = Depends(get_service)):
    return svc.create_experiment(user, body.model_dump())


@router.get("", summary="List my experiments")
async def list_experiments(limit: int = Query(50, ge=1, le=200), user: dict = Depends(get_current_user),
                           svc: ExecutionService = Depends(get_service)) -> Dict[str, List[Dict[str, Any]]]:
    return {"experiments": svc.list_records(user, kind="experiment", limit=limit)}


@router.post("/{experiment_id}/start", status_code=202, summary="Start a created experiment")
async def start_experiment(experiment_id: str, user: dict = Depends(require_role(ROLE_ANALYST)),
                           svc: ExecutionService = Depends(get_service)):
    return svc.start_experiment(user, experiment_id)


@router.get("/{experiment_id}", summary="Experiment status, progress and headline results")
async def get_experiment(experiment_id: str, user: dict = Depends(get_current_user),
                         svc: ExecutionService = Depends(get_service)):
    return svc.get_record(user, experiment_id)


@router.get("/{experiment_id}/result", summary="Full evaluation: baselines, precision/recall/F1, CIs, performance")
async def get_result(experiment_id: str, user: dict = Depends(get_current_user),
                     svc: ExecutionService = Depends(get_service)):
    return svc.experiment_result(user, experiment_id)


@router.get("/{experiment_id}/executions", summary="Drill-down executions sampled from this experiment")
async def experiment_executions(experiment_id: str, user: dict = Depends(get_current_user),
                                svc: ExecutionService = Depends(get_service)):
    svc.get_record(user, experiment_id)
    return {"experiment_id": experiment_id,
            "executions": svc.list_records(user, parent_id=experiment_id, limit=200)}
