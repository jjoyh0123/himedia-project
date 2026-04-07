from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any
import uuid

class Position(BaseModel):
    x: float
    y: float

class Facility(BaseModel):
    id: str = Field(default_factory=lambda: f"FAC-{uuid.uuid4().hex[:6].upper()}")
    type: Literal["sprinkler", "electrical_panel", "fire_hydrant", "pillar", "other"]
    position: Position
    alert_zone_mm: float = Field(default=0.0, description="접근/배치 금지 반경 (mm)")
    confidence: Literal["high", "medium", "low"] = "low"

class Entrance(BaseModel):
    position: Position
    direction: str = Field(default="South", description="예: South, North, 입구 정면 등")
    confidence: Literal["high", "medium", "low"] = "low"

class UsableRange(BaseModel):
    zone_id: str
    polygon_bounds: List[Position]
    allowed_properties: List[str] = []
    constraints_applied: List[str] = []

class FloorPlanData(BaseModel):
    dimensions_mm: Dict[str, Any] = {"width": 20000, "height": 15000}
    outline_vertices: List[Position] = []
    facilities: List[Facility] = []
    entrances: List[Entrance] = []
    user_marking_required: bool = False
    usable_ranges: List[UsableRange] = []

FloorPlanData.model_rebuild()
