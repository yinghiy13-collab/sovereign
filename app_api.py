from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="Sovereign API", version="1.0.0")

# 🚨 1. เปิด CORS เพื่อให้ PWA เรียกใช้งานได้
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/ready")
async def ready():
    return {"status": "ready", "mode": "mock", "opa": "mock-active", "llm": "mock"}

@app.get("/")
async def root():
    return {"message": "Sovereign API is running", "mode": "mock", "docs": "/docs"}

# 🚨 2. เปลี่ยน Endpoint ให้ตรงกับที่ PWA เรียกมา (/v1/generate)
@app.post("/v1/generate")
async def generate(payload: dict):
    prompt = payload.get("prompt", "")
    
    # จำลองการเช็ก OPA
    if "evil" in prompt.lower() or "hack" in prompt.lower():
         return {
             "allow": False, 
             "reasons": ["OPA blocked: Malicious prompt detected"],
             "block_index": 0,
             "block_hash": "0000000000000000",
             "generated_code": None
         }

    # 🚨 3. ส่ง Response กลับไปให้ตรงกับที่ PWA ต้องการแสดงผล
    return {
        "allow": True,
        "reasons": ["OPA Policy satisfied (Mock Mode)"],
        "block_index": 1,
        "block_hash": "a1b2c3d4e5f67890abcdef1234567890",
        "generated_code": f"# [Mock Output] Generated code for prompt: {prompt}\nprint('Hello from Sovereign!')"
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
