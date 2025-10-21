# app.py
# API minimal para o desafio "Zé - parceiros de entrega".
# Comentários: cada linha importante tem uma explicação do que faz e porque.
# Requisitos: Python 3.8+, FastAPI, shapely, rtree.

from typing import Any, Dict, Optional, List
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, validator
import json
import os
import uuid
from shapely.geometry import shape, Point, Polygon, MultiPolygon
from rtree import index as rtree_index
from threading import Lock

DATAFILE = "partners.json"
file_lock = Lock()
partners_store: Dict[str, Dict] = {}
rtree_idx = rtree_index.Index()

class GeoJSONPoint(BaseModel):
    type: str
    coordinates: List[float]
    @validator("type")
    def must_be_point(cls, v):
        if v != "Point":
            raise ValueError("address.type must be 'Point'")
        return v
    @validator("coordinates")
    def coords_len_two(cls, v):
        if not isinstance(v, list) or len(v) != 2:
            raise ValueError("address.coordinates must be [lng, lat]")
        if not all(isinstance(x, (int, float)) for x in v):
            raise ValueError("coordinates must be numbers")
        return v

class GeoJSONMultiPolygon(BaseModel):
    type: str
    coordinates: List
    @validator("type")
    def must_be_multipolygon(cls, v):
        if v != "MultiPolygon":
            raise ValueError("coverageArea.type must be 'MultiPolygon'")
        return v

class PartnerCreate(BaseModel):
    id: Any
    tradingName: str = Field(..., alias="tradingName")
    ownerName: str = Field(..., alias="ownerName")
    document: str
    coverageArea: GeoJSONMultiPolygon = Field(..., alias="coverageArea")
    address: GeoJSONPoint
    class Config:
        allow_population_by_field_name = True

def _id_to_str(pid: Any) -> str:
    return str(pid)

def _rtree_int_id_from_str(sid: str) -> int:
    return abs(hash(sid)) % (2**31 - 1)

def _persist_store():
    with file_lock:
        with open(DATAFILE, "w", encoding="utf-8") as f:
            json.dump(list(partners_store.values()), f, ensure_ascii=False, indent=2)

def _load_store():
    global partners_store, rtree_idx
    partners_store = {}
    rtree_idx = rtree_index.Index()
    if os.path.exists(DATAFILE):
        with open(DATAFILE, "r", encoding="utf-8") as f:
            try:
                items = json.load(f)
            except json.JSONDecodeError:
                items = []
        for item in items:
            sid = _id_to_str(item["id"])
            partners_store[sid] = item
            try:
                cov = shape(item["coverageArea"])
                minx, miny, maxx, maxy = cov.bounds
                rid = _rtree_int_id_from_str(sid)
                rtree_idx.insert(rid, (minx, miny, maxx, maxy), obj=sid)
            except Exception:
                continue

def _parse_coverage_area(geojson_obj: Dict) -> MultiPolygon:
    geom = shape(geojson_obj)
    if isinstance(geom, Polygon):
        geom = MultiPolygon([geom])
    if not isinstance(geom, MultiPolygon):
        raise ValueError("coverageArea must be a MultiPolygon or Polygon")
    if geom.is_empty:
        raise ValueError("coverageArea geometry is empty")
    return geom

def _parse_address_point(geojson_obj: Dict) -> Point:
    geom = shape(geojson_obj)
    if not isinstance(geom, Point):
        raise ValueError("address must be a Point")
    return geom

def _ensure_unique_document(doc: str, excluded_id: Optional[str] = None):
    for sid, item in partners_store.items():
        if excluded_id is not None and sid == excluded_id:
            continue
        if item.get("document") == doc:
            raise HTTPException(status_code=400, detail="document must be unique")

def _insert_partner_into_store(partner_raw: Dict):
    sid = _id_to_str(partner_raw["id"])
    if sid in partners_store:
        raise HTTPException(status_code=400, detail="id already exists")
    _ensure_unique_document(partner_raw["document"])
    try:
        cov = _parse_coverage_area(partner_raw["coverageArea"])
        addr = _parse_address_point(partner_raw["address"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    partners_store[sid] = partner_raw
    rid = _rtree_int_id_from_str(sid)
    minx, miny, maxx, maxy = cov.bounds
    rtree_idx.insert(rid, (minx, miny, maxx, maxy), obj=sid)
    _persist_store()

def _get_partner_by_id(pid: Any) -> Dict:
    sid = _id_to_str(pid)
    if sid not in partners_store:
        raise HTTPException(status_code=404, detail="partner not found")
    return partners_store[sid]

def _find_nearest_partner_including_point(lng: float, lat: float) -> Optional[Dict]:
    p = Point(lng, lat)
    candidates: List[tuple] = []
    for rid in rtree_idx.intersection((lng, lat, lng, lat), objects=True):
        sid = rid.object
        partner = partners_store.get(sid)
        if not partner:
            continue
        try:
            cov = _parse_coverage_area(partner["coverageArea"])
            if cov.contains(p):
                addr = _parse_address_point(partner["address"])
                dist = p.distance(addr)
                candidates.append((dist, partner))
        except Exception:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]

app = FastAPI(title="Ze Partners API - Minimal")
_load_store()

@app.post("/partners", status_code=201)
def create_partner(payload: PartnerCreate):
    raw = json.loads(payload.json(by_alias=True, exclude_none=True))
    _insert_partner_into_store(raw)
    return {"status": "created", "id": raw["id"]}

@app.get("/partners/{partner_id}")
def get_partner(partner_id: str):
    partner = _get_partner_by_id(partner_id)
    return partner

@app.get("/partners/nearest")
def get_nearest_partner(lng: float = Query(..., description="longitude"),
                        lat: float = Query(..., description="latitude")):
    partner = _find_nearest_partner_including_point(lng, lat)
    if not partner:
        raise HTTPException(status_code=404, detail="no partner covers this location")
    return partner

@app.get("/health")
def health():
    return {"status": "ok", "partners_count": len(partners_store)}
