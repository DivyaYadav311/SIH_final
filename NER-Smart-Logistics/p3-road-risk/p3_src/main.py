from fastapi import FastAPI
from p3_src.api import router

app = FastAPI(
    title="Road Intelligence API (Person 3)",
    description="Analyzes road segments for disruption probability and accessibility based on hazards and incidents.",
    version="1.0.0"
)

app.include_router(router, prefix="/api/v1/road-risk")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
