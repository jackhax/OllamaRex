#!/usr/bin/env python

import ghidra_bridge

# Initialize the Ghidra Bridge
bridge = ghidra_bridge.GhidraBridge(namespace=globals(), hook_import=True)

import os
import json
from tqdm import tqdm
from collections import defaultdict

# Ensure all Ghidra classes are available via the bridge
bridge.remote_import("ghidra.app.decompiler")
bridge.remote_import("ghidra.program.model.listing.Function")
bridge.remote_import("ghidra.util.task.ConsoleTaskMonitor")

# Sketchy Ghidra remote imports
# import ghidra.app.decompiler
from ghidra.app.decompiler import DecompInterface, DecompileOptions
from ghidra.util.task import ConsoleTaskMonitor

# Get the current program
currentProgram = bridge.remote_eval("getCurrentProgram()")
# .remote_evaluate("getCurrentProgram()")

# Create output directory
progName = currentProgram.getName()
os.makedirs(progName, exist_ok=True)

# Map function names to their objects
funcNames = {}

# Build the call graph
callGraph = defaultdict(list)
fm = currentProgram.getFunctionManager()
functions = list(fm.getFunctions(True))
for func in tqdm(functions, desc="Building call graph"):
    # Get the function name
    name = func.getName()
    funcNames[name] = func
    for calledFunc in func.getCalledFunctions(ConsoleTaskMonitor()):
        if calledFunc.isThunk(): continue
        calledName = calledFunc.getName()
        if calledName == name: continue
        callGraph[name].append(calledName)
callGraph = dict(callGraph)
for func in functions:
    name = func.getName()
    if name not in callGraph and not func.isThunk():
        callGraph[name] = []

# Decompile all the functions
decompiler = DecompInterface()

# Pull decompiler options from the current program
opt = DecompileOptions()
opt.grabFromProgram(currentProgram)
decompiler.setOptions(opt)

missing = []
decompiler.openProgram(currentProgram)
decomps = {}
for func in tqdm(functions, desc="Decompiling functions"):
    name = func.getName()
    decompResult = decompiler.decompileFunction(func, 0, ConsoleTaskMonitor())
    decompFunc = decompResult.getDecompiledFunction()
    if not decompFunc:
        missing.append(name)
        continue
    decomps[name] = decompFunc.getC()
decompiler.closeProgram()

# Save the decompilations
with open(os.path.join(progName, "decompilations.json"), "w") as f:
    json.dump(decomps, f)
    f.write("\n")

# Remove missing functions from the call graph
for func in missing:
    del callGraph[func]
    for called in callGraph:
        if func in callGraph[called]:
            callGraph[called].remove(func)
print(f"Missing {len(missing)} functions:")
print(missing)

# Save the call graph
with open(os.path.join(progName, "call_graph.json"), "w") as f:
    json.dump(callGraph, f)
    f.write("\n")
