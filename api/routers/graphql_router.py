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

from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/graphql", tags=["GraphQL"])


class GraphQLRequest(BaseModel):
    query: str
    variables: Optional[Dict[str, Any]] = None
    operationName: Optional[str] = None


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def graphql_playground(request: Request):
    """Interactive GraphQL Playground interface for browser users."""
    return HTMLResponse(content="""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>ChronosMesh GraphQL Explorer</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/graphql-playground-react@1.7.42/build/static/css/index.css" />
  <link rel="shortcut icon" href="https://cdn.jsdelivr.net/npm/graphql-playground-react@1.7.42/build/favicon.png" />
  <script src="https://cdn.jsdelivr.net/npm/graphql-playground-react@1.7.42/build/static/js/middleware.js"></script>
  <style>
    body { margin: 0; background: #181E2B; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    #header { padding: 12px 24px; background: #0F131D; color: #fff; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #2B3448; }
    #header h1 { font-size: 16px; margin: 0; font-weight: 600; color: #4ADE80; display: flex; align-items: center; gap: 8px; }
    #header .badge { background: #2B3448; font-size: 12px; padding: 4px 8px; border-radius: 4px; color: #94A3B8; }
    #root { height: calc(100vh - 49px); }
  </style>
</head>
<body>
  <div id="header">
    <h1><span>🕸️</span> ChronosMesh GraphQL Explorer</h1>
    <div class="badge">POST /graphql • Distributed Causality & Neo4j Engine</div>
  </div>
  <div id="root"></div>
  <script>
    window.addEventListener('load', function (event) {
      GraphQLPlayground.init(document.getElementById('root'), {
        endpoint: '/graphql',
        settings: {
          'editor.theme': 'dark',
          'request.credentials': 'same-origin',
        },
        tabs: [
          {
            endpoint: '/graphql',
            headers: { Authorization: 'Bearer <paste the access_token returned by POST /auth/login>' },
            name: 'Causal Ancestors',
            query: '{\\n  ancestors(eventId: "evt-payment-processed") {\\n    event_id\\n    service_id\\n    logical_time\\n  }\\n}',
          },
          {
            endpoint: '/graphql',
            headers: { Authorization: 'Bearer <paste the access_token returned by POST /auth/login>' },
            name: 'Concurrency & DAG',
            query: '{\\n  concurrency {\\n    scenario\\n    concurrent_pairs\\n  }\\n  dag\\n}',
          }
        ]
      })
    })
  </script>
</body>
</html>
""")


@router.post("")
@router.post("/")
async def execute_graphql(
    body: GraphQLRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Executes GraphQL queries against ChronosMesh Causal Engine and Neo4j.
    Supports querying ancestors, descendants, concurrency, and timeline.
    """
    store = get_store(request)
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
