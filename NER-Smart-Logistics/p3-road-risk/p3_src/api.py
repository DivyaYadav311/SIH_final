from fastapi import APIRouter, HTTPException
from p3_src.schemas import RoadRiskRequest, RoadRiskResponse, AnalyzedRoad, P3PredictionRequest, P3PredictionResponse
from p3_src.services.risk_engine import RiskEngine
from p3_src.ml_pipeline.inference import current_model_info, predict_severity_risk
from datetime import datetime, timezone
import uuid

router = APIRouter()
risk_engine = RiskEngine()

@router.post("/analyze", response_model=RoadRiskResponse)
async def analyze_road_risk(request: RoadRiskRequest):
    try:
        analyzed_roads = risk_engine.analyze(
            roads=request.roads,
            hazards=request.hazard_context,
            incidents=request.incidents
        )
        
        response = RoadRiskResponse(
            request_id=request.request_id,
            timestamp=datetime.now(timezone.utc),
            model_version=risk_engine.model_version,
            roads=analyzed_roads
        )
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})

@router.get("/roads/{road_id}", response_model=RoadRiskResponse)
async def get_road_risk(road_id: str):
    # This is a stub for a GET endpoint that would fetch road info and hazards from providers.
    # In a full implementation, it would call OverpassProvider, FloodProvider, IncidentProvider.
    # For now, it returns a 501 Not Implemented because it requires fetching real-time external data.
    raise HTTPException(status_code=501, detail={"code": "NOT_IMPLEMENTED", "message": "GET single road risk not fully implemented yet."})

@router.get("/health")
async def health_check():
    try:
        current_model_info()
        risk_status = "available"
    except (OSError, RuntimeError, ValueError, KeyError):
        risk_status = "unavailable"
    return {
        "status": "ok" if risk_status == "available" else "degraded",
        "service": "road-risk-engine",
        "risk_model_status": risk_status,
        "road_disruption_model_status": "insufficient_labels",
    }

@router.get("/model")
async def model_info():
    try:
        return current_model_info()
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=503, detail={"code": "MODEL_NOT_AVAILABLE", "message": str(exc)})

@router.post("/predict", response_model=P3PredictionResponse)
async def predict(request: P3PredictionRequest):
    values = request.model_dump()
    try:
        result = predict_severity_risk(values)
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=503, detail={"code": "MODEL_NOT_AVAILABLE", "message": str(exc)})
    return P3PredictionResponse(
        road_id=request.road_id,
        timestamp=request.timestamp,
        **result,
    )
