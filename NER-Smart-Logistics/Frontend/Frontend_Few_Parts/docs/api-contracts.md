# P5 API Contracts

## Shipment
`POST /api/v1/shipments`

Input contains shipment fields plus route information from P4. Output contains shipment risk, ETA and status.

## Shortage
`POST /api/v1/predictions/shortage`

Input contains inventory, consumption, incoming supply, ETA, road risk and population. Output contains shortage probability, days to shortage, risk level, confidence and model version.

## Warehouse
`POST /api/v1/warehouses/optimize`

Input contains warehouses and target districts. Output contains source warehouse, destination, quantity and allocation reason.
