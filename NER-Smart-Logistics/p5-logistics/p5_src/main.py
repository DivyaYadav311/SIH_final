from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .logistics import LogisticsService

from .schemas import (
    DemandInput,
    DemandOutput,
    ShipmentInput,
    ShipmentOutput,
    ShortageInput,
    ShortageOutput,
    WarehouseOptimizationInput,
    WarehouseOptimizationOutput,
    WarehouseOutput,
)


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="NER Smart Logistics - P5",
    version="1.1.0",
)


app.add_middleware(
    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


service = LogisticsService()


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "module": "p5-logistics",
        "version": "1.1.0",
        "p4_base_url": service.p4_client.base_url,
    }


# ============================================================
# WAREHOUSES
# ============================================================

@app.get(
    "/api/v1/warehouses",
    response_model=list[WarehouseOutput],
)
def list_warehouses():

    result = []

    for warehouse in service.warehouses.values():

        utilization = (
            service.get_warehouse_utilization(
                warehouse.warehouse_id
            )
        )

        available_capacity = max(
            0,
            warehouse.storage_capacity
            - utilization,
        )

        result.append(
            WarehouseOutput(
                **warehouse.model_dump(
                    exclude={"current_utilization"}
                ),
                current_utilization=utilization,
                available_capacity=available_capacity,
            )
        )

    return result


# ============================================================
# INVENTORY
# ============================================================

@app.get("/api/v1/inventory")
def list_inventory():

    return list(
        service.inventory.values()
    )


@app.get(
    "/api/v1/inventory/{product_type}"
)
def get_product_inventory(
    product_type: str,
):

    return service.get_inventory_for_product(
        product_type
    )


# ============================================================
# SHIPMENTS
# ============================================================

@app.post(
    "/api/v1/shipments",
    response_model=ShipmentOutput,
)
def create_shipment(
    payload: ShipmentInput,
):

    try:

        return service.create_shipment(
            payload
        )

    except RuntimeError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.get(
    "/api/v1/shipments",
    response_model=list[ShipmentOutput],
)
def list_shipments():

    return list(
        service.shipments.values()
    )


# ============================================================
# DEMAND PREDICTION
# ============================================================

@app.post(
    "/api/v1/predictions/demand",
    response_model=DemandOutput,
)
def demand_prediction(
    payload: DemandInput,
):

    try:

        return service.predict_demand(
            payload
        )

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# SHORTAGE PREDICTION
# ============================================================

@app.post(
    "/api/v1/predictions/shortage",
    response_model=ShortageOutput,
)
def shortage_prediction(
    payload: ShortageInput,
):

    try:

        return service.predict_shortage(
            payload
        )

    except RuntimeError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ============================================================
# WAREHOUSE OPTIMIZATION
# ============================================================

@app.post(
    "/api/v1/warehouses/optimize",
    response_model=WarehouseOptimizationOutput,
)
def warehouse_optimization(
    payload: WarehouseOptimizationInput,
):

    try:

        return service.optimize_warehouses(
            payload
        )

    except RuntimeError as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

