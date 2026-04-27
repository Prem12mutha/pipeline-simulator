from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class Instruction(BaseModel):
    id: int
    raw: str
    op: str
    dest: Optional[str] = None
    src1: Optional[str] = None
    src2: Optional[str] = None
    target_label: Optional[str] = None
    is_branch: bool = False
    is_jump: bool = False
    is_memory: bool = False
    is_store: bool = False

class StageInfo(BaseModel):
    stage: str
    cycle: int
    stalled: bool = False
    forwarded_from: Optional[str] = None
    flushed: bool = False

class HazardExplanation(BaseModel):
    cycle: int
    instruction_id: int
    hazard_type: str # RAW, WAR, WAW, CONTROL
    description: str

class ExecutionTrace(BaseModel):
    instruction_id: int
    raw: str
    stages: List[StageInfo]

class SimulationResult(BaseModel):
    traces: List[ExecutionTrace]
    explanations: List[HazardExplanation]
    total_cycles: int
    cpi: float
    stalls: int
    flushes: int
