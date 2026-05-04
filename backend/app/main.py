from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(
    title="Adaptive API Security Mesh",
    description="Intelligent backend-driven API security platform",
    version="1.0.0"
)

app.include_router(router)


@app.get("/")
def root():
    return {"message": "Adaptive API Security Mesh is running"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}