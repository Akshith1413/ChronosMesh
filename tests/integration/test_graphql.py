"""
Integration tests for ChronosMesh GraphQL API.
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.auth import create_access_token


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    token = create_access_token(data={"sub": "guru", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


def test_graphql_schema_info(client, auth_headers):
    query = """
    query {
      schema
    }
    """
    response = client.post("/graphql", json={"query": query}, headers=auth_headers)
    assert response.status_code == 200
    res_data = response.json()
    assert "data" in res_data
    assert "schema" in res_data["data"]


def test_graphql_concurrency_query(client, auth_headers):
    # Load demo scenario first
    client.post("/api/scenarios/order_payment_flow/load", headers=auth_headers)

    query = """
    query {
      concurrency {
        scenario
        concurrent_pairs
      }
    }
    """
    response = client.post("/graphql", json={"query": query}, headers=auth_headers)
    assert response.status_code == 200
    res_data = response.json()
    assert "data" in res_data
    assert "concurrency" in res_data["data"]


def test_graphql_dag_query(client, auth_headers):
    query = """
    query {
      dag {
        nodes
        links
      }
    }
    """
    response = client.post("/api/graphql", json={"query": query}, headers=auth_headers)
    assert response.status_code == 200
    res_data = response.json()
    assert "data" in res_data
    assert "dag" in res_data["data"]
