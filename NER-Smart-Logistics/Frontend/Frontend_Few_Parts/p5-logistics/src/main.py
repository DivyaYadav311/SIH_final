from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .schemas import ShipmentInput, ShipmentOutput, ShortageInput, ShortageOutput, WarehouseOptimizationInput, WarehouseOptimizationOutput
from .logistics import LogisticsService

app = FastAPI(title="NER Smart Logistics - P5", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
service = LogisticsService()

@app.get("/health")
def health():
    return {"status": "ok", "module": "p5-logistics", "version": "1.0.0"}

@app.post("/api/v1/shipments", response_model=ShipmentOutput)
def create_shipment(payload: ShipmentInput):
    return service.create_shipment(payload)

@app.get("/api/v1/shipments", response_model=list[ShipmentOutput])
def list_shipments():
    return list(service.shipments.values())

@app.post("/api/v1/predictions/shortage", response_model=ShortageOutput)
def shortage_prediction(payload: ShortageInput):
    return service.predict_shortage(payload)

@app.post("/api/v1/warehouses/optimize", response_model=WarehouseOptimizationOutput)
def warehouse_optimization(payload: WarehouseOptimizationInput):
    return service.optimize_warehouses(payload)
