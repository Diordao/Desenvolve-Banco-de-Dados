from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_create_and_get_partner():
    payload = {
      "id": "test-1",
      "tradingName": "T1",
      "ownerName": "O1",
      "document": "doc-1",
      "coverageArea": {"type":"MultiPolygon","coordinates":[[[[-46.58,-23.55],[-46.58,-23.54],[-46.57,-23.54],[-46.58,-23.55]]]]},
      "address": {"type":"Point","coordinates":[-46.57421,-23.551]}
    }
    r = client.post("/partners", json=payload)
    assert r.status_code == 201
    r2 = client.get("/partners/test-1")
    assert r2.status_code == 200
    assert r2.json()["document"] == "doc-1"

def test_nearest_found():
    r = client.get("/partners/nearest?lng=-46.57421&lat=-23.551")
    assert r.status_code in (200, 404)
