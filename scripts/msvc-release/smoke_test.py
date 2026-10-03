"""Run a small excited cavity to check an extracted Windows installation."""
import argparse
import gc
import os
from pathlib import Path
import shutil
import uuid

import numpy as np
from CSXCAD import ContinuousStructure
from openEMS import openEMS

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--engine', choices=('multithreaded', 'vulkan'), default='multithreaded')
args = parser.parse_args()
original = Path.cwd()
output = original / ('openems-check-' + uuid.uuid4().hex)
output.mkdir()
csx = ContinuousStructure()
grid = csx.GetGrid()
grid.SetDeltaUnit(1e-3)
for axis in 'xyz':
    grid.SetLines(axis, np.linspace(-20, 20, 21))
fdtd = openEMS(NrTS=100, EndCriteria=0)
fdtd.SetCSX(csx)
fdtd.SetGaussExcite(1e9, 0.5e9)
fdtd.SetBoundaryCond(['PEC'] * 6)
fdtd.AddLumpedPort(1, 50, [-2, -2, -2], [2, 2, 2], 'z', 1)
try:
    result = fdtd.Run(str(output / 'simulation'), engine=args.engine, numThreads=2)
    assert result in (None, 0), result
    signal = np.loadtxt(output / 'simulation/port_ut_1', comments='%')
    assert signal.shape[0] > 1
    assert np.isfinite(signal).all()
    assert np.max(np.abs(signal[:, 1])) > 0
    print('PASS: installed bindings and {} simulation'.format(args.engine))
finally:
    del fdtd
    gc.collect()
    os.chdir(original)
    shutil.rmtree(output)
