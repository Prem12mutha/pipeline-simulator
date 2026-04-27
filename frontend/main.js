// No external icons

// DOM Elements
const editor = document.getElementById('code-editor');
const lineNumbers = document.getElementById('line-numbers');
const sampleSelect = document.getElementById('sample-select');
const modeBtns = document.querySelectorAll('.mode-btn');

const btnRun = document.getElementById('btn-run');
const btnStep = document.getElementById('btn-step');
const btnReset = document.getElementById('btn-reset');

const valCycles = document.getElementById('val-cycles');
const valCpi = document.getElementById('val-cpi');
const valStalls = document.getElementById('val-stalls');
const valFlushes = document.getElementById('val-flushes');

const vizContainer = document.getElementById('viz-container');
const explanationsList = document.getElementById('explanations-list');

// State
let currentMode = 'none';
let simulationData = null;
let currentCycle = 0;
let isStepping = false;

// Samples
const samples = {
    custom: '',
    raw: `ADD R1, R2, R3\nSUB R4, R1, R5\nMUL R6, R1, R7`,
    load_use: `LOAD R1, 10(R2)\nADD R3, R1, R4`,
    branch: `ADD R1, R2, R3\nBEQ R1, R0, LABEL\nADD R4, R5, R6\nLABEL:\nSUB R7, R8, R9`,
    waw: `ADD R1, R2, R3\nSUB R1, R4, R5`
};

// Editor Sync
editor.addEventListener('input', updateLineNumbers);
editor.addEventListener('scroll', () => {
    lineNumbers.scrollTop = editor.scrollTop;
});

function updateLineNumbers() {
    const lines = editor.value.split('\n').length;
    lineNumbers.innerHTML = Array(lines).fill(0).map((_, i) => i + 1).join('<br>');
}

// Initialize with default sample
editor.value = samples['raw'];
sampleSelect.value = 'raw';
updateLineNumbers();
setTimeout(() => runSimulation(false), 500); // Auto-run on load

sampleSelect.addEventListener('change', (e) => {
    editor.value = samples[e.target.value];
    updateLineNumbers();
    resetSimulation();
});

// Mode Toggle
modeBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
        modeBtns.forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        currentMode = e.target.dataset.mode;
        if (simulationData) {
            runSimulation(false); // Re-run quietly
        }
    });
});

// Controls
btnRun.addEventListener('click', () => runSimulation(false));
btnStep.addEventListener('click', () => {
    if (!simulationData || !isStepping) {
        runSimulation(true);
    } else {
        stepSimulation();
    }
});
btnReset.addEventListener('click', resetSimulation);

async function runSimulation(stepping = false) {
    const code = editor.value.trim();
    if (!code) {
        alert("Please enter some assembly code first.");
        return;
    }

    btnRun.disabled = true;
    btnStep.disabled = true;
    
    try {
        const response = await fetch('http://127.0.0.1:8000/api/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, mode: currentMode })
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert("Error: " + data.error);
            return;
        }
        
        simulationData = data;
        isStepping = stepping;
        currentCycle = stepping ? 1 : data.total_cycles;
        
        renderState();
        
    } catch (err) {
        alert("Failed to connect to backend. Is the server running?");
        console.error(err);
    } finally {
        btnRun.disabled = false;
        btnStep.disabled = false;
    }
}

function stepSimulation() {
    if (simulationData && currentCycle < simulationData.total_cycles) {
        currentCycle++;
        renderState();
    } else {
        isStepping = false;
    }
}

function resetSimulation() {
    simulationData = null;
    currentCycle = 0;
    isStepping = false;
    valCycles.textContent = '0';
    valCpi.textContent = '0.0';
    valStalls.textContent = '0';
    valFlushes.textContent = '0';
    vizContainer.innerHTML = '<div class="empty-state">Run simulation to view pipeline</div>';
    explanationsList.innerHTML = '<div class="empty-state text-sm">No hazards detected yet.</div>';
}

function renderState() {
    if (!simulationData) return;
    
    // Update Metrics (only up to current cycle if stepping)
    // To be precise, we show final metrics if not stepping, or proportional if stepping
    valCycles.textContent = currentCycle;
    
    if (!isStepping || currentCycle === simulationData.total_cycles) {
        valCpi.textContent = simulationData.cpi;
        valStalls.textContent = simulationData.stalls;
        valFlushes.textContent = simulationData.flushes;
    } else {
        valCpi.textContent = '-';
        valStalls.textContent = '-';
        valFlushes.textContent = '-';
    }

    // Render Grid
    renderGrid();
    
    // Render Explanations
    renderExplanations();
}

function renderGrid() {
    const traces = simulationData.traces;
    if (traces.length === 0) return;
    
    let html = '<table class="grid-table"><thead><tr><th class="inst-col">Instruction</th>';
    for (let c = 1; c <= currentCycle; c++) {
        html += `<th>C${c}</th>`;
    }
    html += '</tr></thead><tbody>';
    
    traces.forEach(trace => {
        html += `<tr><td class="inst-col">${trace.raw}</td>`;
        
        let lastStage = null;
        for (let c = 1; c <= currentCycle; c++) {
            const stageInfo = trace.stages.find(s => s.cycle === c);
            if (stageInfo) {
                let classes = `stage-cell stage-${stageInfo.stage}`;
                let content = stageInfo.stage;
                if (stageInfo.stalled) {
                    classes = 'stage-cell stage-stall';
                    content = 'ST';
                } else if (stageInfo.flushed) {
                    classes = 'stage-cell stage-flush';
                }
                
                // We'll add IDs to cells for drawing forwarding lines later
                const cellId = `cell-${trace.instruction_id}-${c}`;
                
                // Hazard highlights logic (simple representation based on explanations)
                const hazardForThisInstAndCycle = simulationData.explanations.find(e => 
                    e.instruction_id === trace.instruction_id && e.cycle === c
                );
                
                if (hazardForThisInstAndCycle) {
                    if (hazardForThisInstAndCycle.hazard_type.includes('RAW')) classes += ' hazard-border-RAW';
                    else if (hazardForThisInstAndCycle.hazard_type === 'WAR') classes += ' hazard-border-WAR';
                    else if (hazardForThisInstAndCycle.hazard_type === 'WAW') classes += ' hazard-border-WAW';
                }
                
                html += `<td class="${classes}" id="${cellId}" data-fwd="${stageInfo.forwarded_from || ''}">${content}</td>`;
                lastStage = stageInfo;
            } else {
                html += '<td></td>';
            }
        }
        html += '</tr>';
    });
    
    html += '</tbody></table>';
    vizContainer.innerHTML = html;
    
    // Scroll to right if stepping
    if (isStepping) {
        vizContainer.scrollLeft = vizContainer.scrollWidth;
    }
    
    // Draw Forwarding Paths
    setTimeout(drawForwardingPaths, 50); // Small timeout to ensure DOM is rendered
}

function drawForwardingPaths() {
    // Remove existing SVG overlays
    const existing = document.getElementById('forwarding-overlay');
    if (existing) existing.remove();
    
    if (currentMode !== 'forwarding') return;
    
    const svgNS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNS, "svg");
    svg.id = 'forwarding-overlay';
    svg.style.position = 'absolute';
    svg.style.top = '0';
    svg.style.left = '0';
    svg.style.width = '100%';
    svg.style.height = '100%';
    svg.style.pointerEvents = 'none';
    svg.style.zIndex = '50';
    
    // Add arrow marker
    const defs = document.createElementNS(svgNS, "defs");
    const marker = document.createElementNS(svgNS, "marker");
    marker.setAttribute("id", "arrowhead");
    marker.setAttribute("markerWidth", "10");
    marker.setAttribute("markerHeight", "7");
    marker.setAttribute("refX", "9");
    marker.setAttribute("refY", "3.5");
    marker.setAttribute("orient", "auto");
    
    const polygon = document.createElementNS(svgNS, "polygon");
    polygon.setAttribute("points", "0 0, 10 3.5, 0 7");
    polygon.setAttribute("fill", "var(--accent-primary)");
    marker.appendChild(polygon);
    defs.appendChild(marker);
    svg.appendChild(defs);
    
    const traces = simulationData.traces;
    const table = vizContainer.querySelector('.grid-table');
    if (!table) return;
    
    const vizRect = vizContainer.getBoundingClientRect();
    
    traces.forEach((trace, traceIndex) => {
        trace.stages.forEach(stage => {
            if (stage.cycle <= currentCycle && stage.forwarded_from) {
                // Determine source cell based on forwarded_from type
                // EX/MEM: forwarded from EX stage in cycle-1 of an older instruction
                // MEM/WB: forwarded from MEM stage in cycle-1 of an older instruction
                const destCellId = `cell-${trace.instruction_id}-${stage.cycle}`;
                const destCell = document.getElementById(destCellId);
                
                if (!destCell) return;
                
                // Find the source cell
                let sourceCell = null;
                const srcCycle = stage.cycle - 1;
                const srcStageStr = stage.forwarded_from === "EX/MEM" ? "EX" : "MEM";
                
                // Look for the source cell in the traces above
                for (let i = 0; i < traceIndex; i++) {
                    const olderTrace = traces[i];
                    const srcStage = olderTrace.stages.find(s => s.cycle === srcCycle && s.stage === srcStageStr);
                    if (srcStage) {
                        sourceCell = document.getElementById(`cell-${olderTrace.instruction_id}-${srcCycle}`);
                        if (sourceCell) break;
                    }
                }
                
                if (sourceCell && destCell) {
                    const srcRect = sourceCell.getBoundingClientRect();
                    const destRect = destCell.getBoundingClientRect();
                    
                    // Coordinates relative to vizContainer
                    const startX = srcRect.right - vizRect.left;
                    const startY = srcRect.top + (srcRect.height / 2) - vizRect.top;
                    
                    const endX = destRect.left - vizRect.left;
                    const endY = destRect.top + (destRect.height / 2) - vizRect.top;
                    
                    const path = document.createElementNS(svgNS, "path");
                    // Draw a curved line
                    const d = `M ${startX} ${startY} C ${startX + 15} ${startY}, ${endX - 15} ${endY}, ${endX} ${endY}`;
                    path.setAttribute("d", d);
                    path.setAttribute("fill", "none");
                    path.setAttribute("stroke", "var(--accent-primary)");
                    path.setAttribute("stroke-width", "2");
                    path.setAttribute("marker-end", "url(#arrowhead)");
                    
                    svg.appendChild(path);
                }
            }
        });
    });
    
    vizContainer.appendChild(svg);
}

function renderExplanations() {
    if (!simulationData || simulationData.explanations.length === 0) {
        explanationsList.innerHTML = '<div class="empty-state text-sm">No hazards detected.</div>';
        return;
    }
    
    let html = '';
    const relevantExps = simulationData.explanations.filter(e => e.cycle <= currentCycle);
    
    if (relevantExps.length === 0) {
        explanationsList.innerHTML = '<div class="empty-state text-sm">No hazards detected yet.</div>';
        return;
    }
    
    // Sort reverse chronological
    relevantExps.sort((a, b) => b.cycle - a.cycle).forEach(exp => {
        const typeClass = exp.hazard_type.includes('RAW') ? 'RAW' : exp.hazard_type;
        html += `
            <div class="explanation-item type-${typeClass}">
                <span class="explanation-cycle">Cycle ${exp.cycle}</span>
                ${exp.description}
            </div>
        `;
    });
    
    explanationsList.innerHTML = html;
}
