"""
src/interface.py - FastAPI Microservice & Swagger (EXPLAINABLE_AI_INFERENCE Paradigm).
Inference and explainability service for prosigliere_analytics_engineer_bridge_project.
"""

from fastapi import FastAPI
from pydantic import BaseModel
from src.core_engine import create_engine

app = FastAPI(
    title="PROSIGLIERE_ANALYTICS_ENGINEER_BRIDGE_PROJECT - Explainability API",
    description="Prosigliere requires an enterprise-grade Causal & Survival Lifecycle Analytics architecture under Analytics Engineer to solve operational latency, res",
    version="1.0.0",
)

@app.get("/health")
def health_check():
    return {"status": "healthy", "project_id": "GP-197"}

@app.get("/metrics/summary")
def get_metrics_summary():
    engine = create_engine()
    df = engine.execute_analysis()
    return df.to_dict(orient="records")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)