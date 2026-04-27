from typing import List, Dict, Tuple, Optional
from .models import Instruction, ExecutionTrace, StageInfo, HazardExplanation, SimulationResult

class PipelineSimulator:
    def __init__(self, instructions: List[Instruction], labels: Dict[str, int], mode: str):
        self.instructions = instructions
        self.labels = labels
        self.mode = mode # 'none', 'stall', 'forwarding'
        self.pc = 0
        self.cycle = 1
        
        # Pipeline stages hold the instruction currently in that stage
        self.pipeline: Dict[str, Optional[Instruction]] = {
            "IF": None, "ID": None, "EX": None, "MEM": None, "WB": None
        }
        
        self.traces: Dict[int, ExecutionTrace] = {}
        for inst in instructions:
            self.traces[inst.id] = ExecutionTrace(instruction_id=inst.id, raw=inst.raw, stages=[])
            
        self.explanations: List[HazardExplanation] = []
        
        self.stalls = 0
        self.flushes = 0
        
    def get_read_registers(self, inst: Instruction) -> List[str]:
        regs = []
        if inst.src1: regs.append(inst.src1)
        if inst.src2: regs.append(inst.src2)
        return regs
        
    def get_write_register(self, inst: Instruction) -> Optional[str]:
        if inst.op in ['ADD', 'SUB', 'MUL', 'LOAD']:
            return inst.dest
        return None
        
    def check_hazards(self) -> Tuple[bool, bool]:
        """Returns (should_stall, load_use_stall)"""
        id_inst = self.pipeline["ID"]
        if not id_inst:
            return False, False
            
        read_regs = self.get_read_registers(id_inst)
        if not read_regs:
            return False, False
            
        # Check against older instructions in EX, MEM, WB
        older_stages = ["EX", "MEM", "WB"]
        
        should_stall = False
        load_use_stall = False
        
        for stage in older_stages:
            older_inst = self.pipeline[stage]
            if not older_inst:
                continue
                
            write_reg = self.get_write_register(older_inst)
            if write_reg and write_reg in read_regs:
                # RAW Hazard Detected
                self.explanations.append(HazardExplanation(
                    cycle=self.cycle,
                    instruction_id=id_inst.id,
                    hazard_type="RAW",
                    description=f"RAW hazard: Inst {id_inst.id} reads {write_reg} written by Inst {older_inst.id} (in {stage})."
                ))
                
                if self.mode == "stall":
                    should_stall = True
                elif self.mode == "forwarding":
                    if stage == "EX" and older_inst.op == "LOAD":
                        # Load-use hazard requires 1 cycle stall even with forwarding
                        load_use_stall = True
                        self.explanations.append(HazardExplanation(
                            cycle=self.cycle,
                            instruction_id=id_inst.id,
                            hazard_type="RAW (Load-Use)",
                            description=f"Load-Use hazard: Inst {id_inst.id} needs {write_reg} from LOAD Inst {older_inst.id}."
                        ))
                    else:
                        # Forwarding handles it
                        pass
        
        # Detect WAR and WAW just for reporting
        write_reg = self.get_write_register(id_inst)
        if write_reg:
            for stage in older_stages:
                older_inst = self.pipeline[stage]
                if not older_inst: continue
                # WAR
                if write_reg in self.get_read_registers(older_inst):
                    self.explanations.append(HazardExplanation(
                        cycle=self.cycle,
                        instruction_id=id_inst.id,
                        hazard_type="WAR",
                        description=f"WAR hazard: Inst {id_inst.id} writes {write_reg} read by Inst {older_inst.id}."
                    ))
                # WAW
                if write_reg == self.get_write_register(older_inst):
                    self.explanations.append(HazardExplanation(
                        cycle=self.cycle,
                        instruction_id=id_inst.id,
                        hazard_type="WAW",
                        description=f"WAW hazard: Inst {id_inst.id} writes {write_reg} also written by Inst {older_inst.id}."
                    ))

        return should_stall, load_use_stall

    def run(self) -> SimulationResult:
        while self.pc < len(self.instructions) or any(inst is not None for inst in self.pipeline.values()):
            # Check Hazards in ID
            should_stall, load_use_stall = False, False
            if self.mode != "none":
                should_stall, load_use_stall = self.check_hazards()
                
            is_stalled = should_stall or load_use_stall
            
            # Record state for this cycle
            if self.pipeline["WB"]:
                self.traces[self.pipeline["WB"].id].stages.append(StageInfo(stage="WB", cycle=self.cycle))
            if self.pipeline["MEM"]:
                # If there's forwarding from MEM to EX
                fwd = None
                if self.mode == "forwarding" and self.pipeline["EX"]:
                    mem_w = self.get_write_register(self.pipeline["MEM"])
                    ex_r = self.get_read_registers(self.pipeline["EX"])
                    if mem_w and mem_w in ex_r: fwd = "MEM/WB"
                self.traces[self.pipeline["MEM"].id].stages.append(StageInfo(stage="MEM", cycle=self.cycle, forwarded_from=fwd))
            if self.pipeline["EX"]:
                fwd = None
                if self.mode == "forwarding" and self.pipeline["ID"] and not is_stalled:
                    ex_w = self.get_write_register(self.pipeline["EX"])
                    id_r = self.get_read_registers(self.pipeline["ID"])
                    if ex_w and ex_w in id_r and self.pipeline["EX"].op != "LOAD": fwd = "EX/MEM"
                self.traces[self.pipeline["EX"].id].stages.append(StageInfo(stage="EX", cycle=self.cycle, forwarded_from=fwd))
            
            if self.pipeline["ID"]:
                self.traces[self.pipeline["ID"].id].stages.append(StageInfo(stage="ID", cycle=self.cycle, stalled=is_stalled))
            if self.pipeline["IF"]:
                self.traces[self.pipeline["IF"].id].stages.append(StageInfo(stage="IF", cycle=self.cycle, stalled=is_stalled))

            # Move pipeline forward (Reverse order)
            # WB leaves
            self.pipeline["WB"] = self.pipeline["MEM"]
            
            # MEM leaves to WB
            self.pipeline["MEM"] = self.pipeline["EX"]
            
            # EX processing (including Branch Resolution)
            # If Branch is in EX, we resolve it. Predict Not Taken means we just fetched PC+1.
            # If taken, we must flush IF and ID.
            branch_taken = False
            if self.pipeline["EX"] and (self.pipeline["EX"].is_branch or self.pipeline["EX"].is_jump):
                # We simulate taking the branch always for JMP, or conditionally for BEQ
                # For simulation purposes without real registers, we assume branch is always taken if backward, 
                # or we just assume all branches are taken to demonstrate flush.
                # Let's say all branches/jumps are taken for the demo.
                branch_taken = True
                self.pc = self.labels.get(self.pipeline["EX"].target_label, self.pc)
                self.flushes += 2
                
                self.explanations.append(HazardExplanation(
                    cycle=self.cycle,
                    instruction_id=self.pipeline["EX"].id,
                    hazard_type="CONTROL",
                    description=f"Branch Taken! Flushing pipeline."
                ))
                
                # Mark flushed in traces
                if self.pipeline["ID"]: self.traces[self.pipeline["ID"].id].stages[-1].flushed = True
                if self.pipeline["IF"]: self.traces[self.pipeline["IF"].id].stages[-1].flushed = True
                
                self.pipeline["ID"] = None
                self.pipeline["IF"] = None
                
            if not is_stalled:
                if not branch_taken:
                    self.pipeline["EX"] = self.pipeline["ID"]
                    self.pipeline["ID"] = self.pipeline["IF"]
                    
                    # Fetch new instruction
                    if self.pc < len(self.instructions):
                        self.pipeline["IF"] = self.instructions[self.pc]
                        self.pc += 1
                    else:
                        self.pipeline["IF"] = None
            else:
                self.stalls += 1
                self.pipeline["EX"] = None # Bubble
                
            self.cycle += 1
            
            # Prevent infinite loops in simulation
            if self.cycle > 1000:
                break
                
        total_instructions = len(self.instructions)
        cpi = (self.cycle - 1) / total_instructions if total_instructions > 0 else 0
        
        return SimulationResult(
            traces=list(self.traces.values()),
            explanations=self.explanations,
            total_cycles=self.cycle - 1,
            cpi=round(cpi, 2),
            stalls=self.stalls,
            flushes=self.flushes
        )
