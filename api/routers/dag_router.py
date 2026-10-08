"""DAG router — query the reconstructed causal graph."""

from fastapi import APIRouter, Depends, HTTPException

import networkx as nx

from api.auth import get_current_user
from api.store import ChronosMeshStore, get_store

router = APIRouter()


@router.get("/", summary="Get the full causal DAG")
async def get_dag(
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """Return the complete reconstructed causal DAG as node/edge JSON for D3.js."""
    return store.get_dag_json()


@router.get("/roots", summary="Get root events (no causal parents)")
async def get_roots(
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    if not store.events:
        return {"roots": []}
    roots = store._builder.get_roots()
    root_data = [
        dict(store.dag.nodes[r]) | {"id": r}
        for r in roots
        if r in store.dag.nodes
    ]
    return {"roots": root_data}


@router.get("/leaves", summary="Get leaf events (no causal children)")
async def get_leaves(
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    if not store.events:
        return {"leaves": []}
    leaves = store._builder.get_leaves()
    leaf_data = [
        dict(store.dag.nodes[l]) | {"id": l}
        for l in leaves
        if l in store.dag.nodes
    ]
    return {"leaves": leaf_data}


@router.get("/timeline", summary="Get topological causal ordering")
async def get_timeline(
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """Returns events in topological sort order — the true causal execution timeline."""
    topo = store._safe_topo()
    eid_map = {e.event_id: e.to_dict() for e in store.events}
    events_in_order = [
        {"step": i + 1, **eid_map[eid]}
        for i, eid in enumerate(topo)
        if eid in eid_map
    ]
    return {
        "timeline": events_in_order,
        "total_steps": len(events_in_order),
    }


@router.get("/ancestors/{event_id}", summary="Get all causal ancestors of an event")
async def get_ancestors(
    event_id: str,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    if event_id not in store.dag:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not in DAG")
    ancestors = list(nx.ancestors(store.dag, event_id))
    anc_data = [dict(store.dag.nodes[a]) | {"id": a} for a in ancestors]
    return {
        "event_id": event_id,
        "ancestors": anc_data,
        "count": len(anc_data),
    }


@router.get("/descendants/{event_id}", summary="Get all causal descendants of an event")
async def get_descendants(
    event_id: str,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    if event_id not in store.dag:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not in DAG")
    descendants = list(nx.descendants(store.dag, event_id))
    desc_data = [dict(store.dag.nodes[d]) | {"id": d} for d in descendants]
    return {
        "event_id": event_id,
        "descendants": desc_data,
        "count": len(desc_data),
    }


@router.get("/neighbors/{event_id}", summary="Get immediate parents and children")
async def get_neighbors(
    event_id: str,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    if event_id not in store.dag:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not in DAG")
    parents = list(store.dag.predecessors(event_id))
    children = list(store.dag.successors(event_id))
    return {
        "event_id": event_id,
        "immediate_parents": parents,
        "immediate_children": children,
    }
