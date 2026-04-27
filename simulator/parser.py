import re
from typing import List, Tuple, Dict
from .models import Instruction

def parse_assembly(code: str) -> Tuple[List[Instruction], Dict[str, int]]:
    lines = code.strip().split('\n')
    instructions = []
    labels = {}
    
    inst_id = 1
    for line in lines:
        line = line.split('#')[0].strip() # remove comments
        if not line:
            continue
            
        # check for label
        if ':' in line:
            label_part, inst_part = line.split(':', 1)
            labels[label_part.strip()] = inst_id - 1 # target index
            line = inst_part.strip()
            if not line:
                continue
                
        parts = re.split(r'[\s,]+', line)
        op = parts[0].upper()
        
        inst = Instruction(id=inst_id, raw=line, op=op)
        
        # R-type: ADD, SUB, MUL (dest, src1, src2)
        if op in ['ADD', 'SUB', 'MUL']:
            if len(parts) >= 4:
                inst.dest = parts[1]
                inst.src1 = parts[2]
                inst.src2 = parts[3]
                
        # I-type: LOAD (dest, offset(base))
        elif op == 'LOAD':
            if len(parts) >= 3:
                inst.dest = parts[1]
                # parse offset(base) -> base
                mem_op = parts[2]
                base = re.search(r'\((.*?)\)', mem_op)
                if base:
                    inst.src1 = base.group(1)
                inst.is_memory = True
                
        # I-type: STORE (src, offset(base))
        elif op == 'STORE':
            if len(parts) >= 3:
                inst.src1 = parts[1]
                mem_op = parts[2]
                base = re.search(r'\((.*?)\)', mem_op)
                if base:
                    inst.src2 = base.group(1)
                inst.is_memory = True
                inst.is_store = True
                
        # Branch: BEQ (src1, src2, label)
        elif op == 'BEQ':
            if len(parts) >= 4:
                inst.src1 = parts[1]
                inst.src2 = parts[2]
                inst.target_label = parts[3]
                inst.is_branch = True
                
        # Jump: JMP (label)
        elif op == 'JMP':
            if len(parts) >= 2:
                inst.target_label = parts[1]
                inst.is_jump = True
                
        instructions.append(inst)
        inst_id += 1
        
    return instructions, labels
