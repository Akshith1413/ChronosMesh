import asyncio
import json
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from api.auth import get_current_user
from api.store import ChronosMeshStore, get_store

router = APIRouter()


@router.get("/", summary="Get all events (causal emission order)")
async def get_events(
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """Return all events in causal emission order."""
    return {
        "events": store.get_events_json(),
        "count": len(store.events),
        "scenario": store.current_scenario,
    }


@router.get("/arrival", summary="Get events in simulated arrival order")
async def get_arrival_order(
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """Return events in the order they 'arrived' at ChronosMesh (simulating out-of-order Kafka delivery)."""
    return {
        "events": store.get_arrival_order_json(),
        "count": len(store.arrival_order),
        "scenario": store.current_scenario,
    }


@router.get("/causal", summary="Get events in reconstructed causal order")
async def get_causal_order(
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    """Return events sorted by topological (causal) order from the reconstructed DAG."""
    topo = store._safe_topo()
    eid_map = {e.event_id: e.to_dict() for e in store.events}
    ordered = [eid_map[eid] for eid in topo if eid in eid_map]
    return {
        "events": ordered,
        "count": len(ordered),
        "topological_order": topo,
    }


@router.get("/stream", summary="Live Server-Sent Events (SSE) feed")
async def event_stream(
    token: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
    store: ChronosMeshStore = Depends(get_store),
):
    """
    Live Server-Sent Events (SSE) stream for real-time dashboard updates.
    Streams existing arrival events, incoming live events from Kafka/Flink,
    and periodic heartbeats.
    """
    async def event_generator():
        sent_count = 0
        live_queue = asyncio.Queue()

        def _on_live_event(event_dict):
            try:
                live_queue.put_nowait(event_dict)
            except Exception:
                pass

        store.add_listener(_on_live_event)

        try:
            # 1. Stream existing events in arrival order
            for evt in store.get_arrival_order_json():
                payload = json.dumps({"type": "event", "data": evt})
                yield f"data: {payload}\n\n"
                sent_count += 1
                if limit is not None and sent_count >= limit:
                    return
                await asyncio.sleep(0.02)

            # 2. Continuous loop: wait for live events or send heartbeats
            while True:
                try:
                    live_event = await asyncio.wait_for(live_queue.get(), timeout=2.0)
                    payload = json.dumps({"type": "event", "data": live_event})
                    yield f"data: {payload}\n\n"
                    sent_count += 1
                    if limit is not None and sent_count >= limit:
                        return
                except asyncio.TimeoutError:
                    hb = json.dumps({
                        "type": "heartbeat",
                        "event_count": len(store.events),
                        "dag_nodes": store.dag.number_of_nodes(),
                        "dag_edges": store.dag.number_of_edges(),
                        "scenario": store.current_scenario,
                    })
                    yield f"data: {hb}\n\n"
                    sent_count += 1
                    if limit is not None and sent_count >= limit:
                        return
        finally:
            store.remove_listener(_on_live_event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{event_id}", summary="Get a single event by ID")
async def get_event(
    event_id: str,
    _: dict = Depends(get_current_user),
    store: ChronosMeshStore = Depends(get_store),
):
    for evt in store.events:
        if evt.event_id == event_id:
            return evt.to_dict()

    # Fallback to Neo4j if in live mode
    if store.data_source == "live" and store.neo4j.is_connected():
        neo_evt = store.neo4j.get_event(event_id)
        if neo_evt:
            return neo_evt

    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")

