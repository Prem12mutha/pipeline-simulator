from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from simulator.parser import parse_assembly
from simulator.pipeline import PipelineSimulator

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SimulationRequest(BaseModel):
    code: str
    mode: str # "none", "stall", "forwarding"

@app.post("/api/simulate")
def simulate(request: SimulationRequest):
    try:
        instructions, labels = parse_assembly(request.code)
        if not instructions:
            return {"error": "No valid instructions provided."}
            
        simulator = PipelineSimulator(instructions, labels, request.mode)
        result = simulator.run()
        
        return result.model_dump()
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
