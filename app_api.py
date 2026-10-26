from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os

app = FastAPI(title="Sovereign API", version="1.0.0")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/ready")
async def ready():
    return {"status": "ready", "mode": "mock", "opa": "mock-active", "llm": "mock"}

@app.get("/")
async def root():
    return {"message": "Sovereign API is running", "mode": "mock", "docs": "/docs"}

@app.post("/api/v1/analyze")
async def analyze(payload: dict):
    prompt = payload.get("prompt", "")
    
    # จำลองการเช็ก OPA
    if "evil" in prompt.lower() or "hack" in prompt.lower():
         return {"status": "DENIED", "allow": False, "reasons": ["OPA blocked: Malicious prompt detected"]}

    return {
        "status": "ok",
        "allow": True,
        "mode": "mock",
        "prompt_received": prompt[:100],
        "response": f"[Mock Response] Received: {prompt}",
        "note": "Mock Mode active. Connect OPA/Ollama endpoints for real execution.",
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
