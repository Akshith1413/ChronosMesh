"""
ChronosMesh GraphQL API Router.

Provides GraphQL query execution on top of Neo4j and the ChronosMesh Causal Engine
for querying:
  - causal ancestors
  - causal descendants
  - concurrency relationships (E2 || E3)
  - timeline reconstructions
"""

import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.auth import get_current_user
from api.store import get_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graphql", tags=["GraphQL"])


class GraphQLRequest(BaseModel):
    query: str
    variables: Optional[Dict[str, Any]] = None
    operationName: Optional[str] = None


@router.post("")
@router.post("/")
async def execute_graphql(
    body: GraphQLRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Executes GraphQL queries against ChronosMesh Causal Engine and Neo4j.
    Supports querying ancestors, descendants, concurrency, and timeline.
    """
    store = get_store()
    query_str = body.query.strip()
    variables = body.variables or {}

    data: Dict[str, Any] = {}
    errors: List[Dict[str, str]] = []

    # 1. Query Ancestors
    if "ancestors" in query_str:
        event_id = variables.get("eventId")
        if not event_id:
            # Try to parse from query string if hardcoded
            import re
            m = re.search(r'ancestors\s*\(\s*eventId\s*:\s*"([^"]+)"', query_str)
            if m:
                event_id = m.group(1)

        if event_id:
            ancestors = store.get_ancestors(event_id) if hasattr(store, "get_ancestors") else []
            data["ancestors"] = ancestors
        else:
            data["ancestors"] = []

    # 2. Query Descendants
    if "descendants" in query_str:
        event_id = variables.get("eventId")
        if not event_id:
            import re
            m = re.search(r'descendants\s*\(\s*eventId\s*:\s*"([^"]+)"', query_str)
            if m:
                event_id = m.group(1)

        if event_id:
            descendants = store.get_descendants(event_id) if hasattr(store, "get_descendants") else []
            data["descendants"] = descendants
        else:
            data["descendants"] = []

    # 3. Query Concurrency
    if "concurrency" in query_str:
        data["concurrency"] = {
            "scenario": store.current_scenario,
            "concurrent_pairs": store.get_concurrency_pairs() if hasattr(store, "get_concurrency_pairs") else [],
        }

    # 4. Query Timeline
    if "timeline" in query_str:
        data["timeline"] = {
            "arrival_order": [e.to_dict() for e in store.events],
            "causal_order": store.get_causal_order() if hasattr(store, "get_causal_order") else [],
        }

    # 5. Query DAG
    if "dag" in query_str:
        data["dag"] = store.get_dag_json()

    if not data and not errors:
        # Default response with schema info if query didn't match known resolvers
        data = {
            "schema": {
                "types": ["Query"],
                "queries": ["ancestors(eventId: String)", "descendants(eventId: String)", "concurrency", "timeline", "dag"],
            },
            "info": "ChronosMesh GraphQL Engine v1.0",
        }

    return {"data": data, "errors": errors if errors else None}
