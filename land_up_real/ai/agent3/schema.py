from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field, validator

class PlacedCoordinate(BaseModel):
    x: float
    y: float

class Dimensions(BaseModel):
    width: float
    height: float

class PlacedObject(BaseModel):
    object_id: str
    dimensions: Dimensions
    placed_coordinates: PlacedCoordinate = Field(description="Center point of the object in mm")
    rotation_degree: int = 0
    facing: Optional[str] = None

class PathwayNode(BaseModel):
    x: float
    y: float

class Pathway(BaseModel):
    path_id: str
    nodes: List[PathwayNode]

class FinalLayoutData(BaseModel):
    placed_objects: List[PlacedObject]
    visitor_pathways: List[Pathway]
    status: str = "success"
    collision_warning: Optional[str] = None
    brand_rules: Optional[Dict] = None
    entrances: List[Dict] = []

# --- Agent 3 Output Schemas (Placement Decision) ---

class PlacementDirective(BaseModel):
    object_type: str
    reference_point: str # north_wall_mid, entrance_zone 등
    direction: Literal["inward", "wall_facing", "entrance_facing", "freestanding"]
    priority: int = 10
    placed_because: str = ""

class Agent3Output(BaseModel):
    placements: List[PlacementDirective]
