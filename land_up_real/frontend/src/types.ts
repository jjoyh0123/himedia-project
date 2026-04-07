export interface Dimensions {
    width: number;
    height: number;
}

export interface PlacedCoordinate {
    x: number;
    y: number;
}

export interface PlacedObject {
    object_id: string;
    dimensions: Dimensions;
    placed_coordinates: PlacedCoordinate;
    rotation_degree: number;
    facing?: string;
}

export interface PathwayNode {
    x: number;
    y: number;
}

export interface Pathway {
    path_id: string;
    nodes: PathwayNode[];
}

export interface Facility {
    id: string;
    type: string;
    position: PlacedCoordinate;
    alert_zone_mm: number;
}

export interface UsableRange {
    polygon_bounds: { x: number; y: number }[];
}

export interface ExtractedValue {
    value: number | string | null;
    confidence: "high" | "medium" | "low" | null;
    source: "manual" | "default" | "user_input" | null;
}

export interface RelationshipRule {
    rule: string;
    confidence: "high" | "medium" | "low" | null;
}

export interface BrandConstraints {
    clearspace_mm: ExtractedValue;
    character_orientation: ExtractedValue;
    prohibited_material: ExtractedValue;
    logo_clearspace_mm: ExtractedValue;
    relationships: RelationshipRule[];
}

export interface BrandRulesWrapper {
    brand: BrandConstraints;
}

export interface ManualMarkingRequiredResponse {
    status: "manual_marking_required";
    brand: BrandConstraints;
}

export interface UserMarking {
    x: number; // 0.0 ~ 1.0 (비율)
    y: number; // 0.0 ~ 1.0 (비율)
    type: "sprinkler" | "fire_hydrant" | "electrical_panel" | "entrance" | "pillar";
}

export interface FinalLayoutData {
    placed_objects: PlacedObject[];
    entrances: any[];
    visitor_pathways: Pathway[];
    status: string;
    collision_warning?: string;
    dimensions_mm?: { width: number; height: number; };
    outline_vertices?: PlacedCoordinate[];
    facilities?: Facility[];
    usable_ranges?: UsableRange[];
    floor_vector_paths?: number[][][];
    brand_rules?: BrandConstraints;
}
