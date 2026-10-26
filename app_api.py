#!/usr/bin/env python3
import json, hashlib, time, requests
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

OPA_URL = "http://localhost:8181/v1/data/sovereign/authz/allow"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "codellama"
LEDGER_FILE = "grc015_audit_ledger.json"

app = FastAPI(title="Sovereign V7.5", version="7.5.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class GenerateRequest(BaseModel):
    prompt: str
    agent_id: str = "agent-developer-01"
    role: str = "algorithmic-trader"
    tool: str = "ollama-code-gen"
    target_egress: str = "localhost"
    target_ip: Optional[str] = "127.0.0.1"

class GenerateResponse(BaseModel):
    status: str
    allow: bool
    reasons: List[str]
    generated_code: Optional[str] = None
    block_index: int
    block_hash: str
    previous_hash: str
    evaluated_at: str

@dataclass
class AuditBlock:
    index: int
    timestamp: str
    action: str
    agent_id: str
    opa_decision: bool
    reasons: List[str]
    prompt: str
    generated_code: Optional[str]
    previous_hash: str
    hash: str = ""

    def calculate_hash(self) -> str:
        payload = {
            "index": self.index, "timestamp": self.timestamp, "action": self.action,
            "agent_id": self.agent_id, "opa_decision": self.opa_decision, "reasons": self.reasons,
            "prompt": self.prompt, "generated_code": self.generated_code or "", "previous_hash": self.previous_hash
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()

class GRC015Ledger:
    def __init__(self, filepath: str = LEDGER_FILE):
        self.filepath = filepath
        self.chain: List[AuditBlock] = []
        self._load_or_init_ledger()

    def _load_or_init_ledger(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.chain = [AuditBlock(**item) for item in json.load(f)]
        except (FileNotFoundError, json.JSONDecodeError):
            genesis = AuditBlock(index=0, timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), action="GENESIS_INIT", agent_id="system-root", opa_decision=True, reasons=["Genesis"], prompt="Init", generated_code="", previous_hash="0"*64)
            genesis.hash = genesis.calculate_hash()
            self.chain = [genesis]
            self._save_to_disk()

    def add_entry(self, action, agent_id, opa_decision, reasons, prompt, generated_code):
        prev = self.chain[-1]
        new_block = AuditBlock(index=len(self.chain), timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), action=action, agent_id=agent_id, opa_decision=opa_decision, reasons=reasons, prompt=prompt, generated_code=generated_code, previous_hash=prev.hash)
        new_block.hash = new_block.calculate_hash()
        self.chain.append(new_block)
        self._save_to_disk()
        return new_block

    def verify_integrity(self):
        for i in range(1, len(self.chain)):
            curr, prev = self.chain[i], self.chain[i-1]
            if curr.previous_hash != prev.hash or curr.hash != curr.calculate_hash(): return False
        return True

    def _save_to_disk(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump([asdict(b) for b in self.chain], f, indent=2, ensure_ascii=False)

ledger_engine = GRC015Ledger()

def evaluate_opa(agent_id, role, tool, target_egress, target_ip):
    payload = {"input": {"agent_id": agent_id, "role": role, "action": "tool.invoke", "tool": tool, "constraints": {"networkAllowlist": ["api.opticodds.com", "localhost", "127.0.0.1"], "targetEgress": target_egress, "targetIP": target_ip, "maxCallsPerHour": 50, "calls_last_hour": 5, "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}}}
    try:
        resp = requests.post(OPA_URL, json=payload, timeout=2.5)
        if resp.status_code == 200:
            res = resp.json().get("result", {})
            if isinstance(res, bool): return {"allow": res, "reasons": ["OPA decision"]}
            return {"allow": res.get("allow", False), "reasons": res.get("reasons", ["OPA eval"])}
        return {"allow": False, "reasons": [f"OPA status {resp.status_code}"]}
    except Exception as e:
        return {"allow": False, "reasons": [f"OPA unreachable: {e}"]}

def generate_ollama_code(prompt):
    payload = {"model": OLLAMA_MODEL, "prompt": f"System: Code only.\nUser: {prompt}\nCode:", "stream": False}
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=45.0)
        return resp.json().get("response", "// No code.") if resp.status_code == 200 else "// Ollama Error"
    except Exception as e: return f"// Error: {e}"

@app.get("/health")
def health(): return {"status": "HEALTHY", "ledger_integrity": ledger_engine.verify_integrity()}

@app.post("/v1/generate", response_model=GenerateResponse)
def generate_code_endpoint(req: GenerateRequest):
    opa_res = evaluate_opa(req.agent_id, req.role, req.tool, req.target_egress, req.target_ip)
    is_allowed, reasons = opa_res.get("allow", False), opa_res.get("reasons", [])
    generated_code = generate_ollama_code(req.prompt) if is_allowed else None
    block = ledger_engine.add_entry("tool.invoke", req.agent_id, is_allowed, reasons, req.prompt, generated_code)
    return GenerateResponse(status="SUCCESS" if is_allowed else "DENIED", allow=is_allowed, reasons=reasons, generated_code=generated_code, block_index=block.index, block_hash=block.hash, previous_hash=block.previous_hash, evaluated_at=block.timestamp)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
