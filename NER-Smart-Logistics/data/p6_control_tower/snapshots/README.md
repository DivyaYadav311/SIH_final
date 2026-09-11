# P6 development snapshots

These JSON files follow the **same field names** as the team API contracts for P4 routes and P5 shipments.

They are **not** a substitute for live IMD, OSM, or production logistics feeds. They exist so the P6 what-if engine and control tower can run before P4/P5 HTTP services are connected.

When `P5_BASE_URL` / `P4_BASE_URL` are set, the engine prefers those APIs and only falls back here if the request fails.
