"""Bounded, non-destructive GPU correctness check; no clock/power changes."""
import json
import subprocess
import time
from pathlib import Path

import torch

report = {"started": time.strftime('%Y-%m-%d %H:%M:%S'), "checks": [], "samples": []}
started = time.monotonic()


def telemetry():
    output = subprocess.check_output([
        'nvidia-smi', '--query-gpu=temperature.gpu,power.draw,memory.used',
        '--format=csv,noheader,nounits'], text=True, timeout=5)
    values = output.strip().splitlines()[0].split(',')
    sample = dict(seconds=round(time.monotonic()-started, 1), temperature=float(values[0]),
                  watts=float(values[1]), memory_mib=float(values[2]))
    report['samples'].append(sample)
    print(json.dumps(sample), flush=True)
    if sample['temperature'] >= 80:
        raise RuntimeError('Stopped at conservative 80 C temperature limit')


try:
    report['gpu'] = torch.cuda.get_device_name(0)
    telemetry()
    # About 512 MiB for patterns and temporary comparisons, leaving display memory free.
    source = torch.arange(32*1024*1024, device='cuda', dtype=torch.int32)
    for pattern in (0, 0x55555555, 0x2AAAAAAA):
        expected = torch.bitwise_xor(source, pattern)
        copied = expected.clone()
        if not torch.equal(copied, expected):
            raise RuntimeError('GPU memory copy mismatch')
        if not torch.equal(torch.bitwise_xor(copied, pattern), source):
            raise RuntimeError('GPU memory pattern mismatch')
    del source, expected, copied
    report['checks'].append('Memory pattern and copy checks passed')
    torch.manual_seed(47)
    torch.backends.cuda.matmul.allow_tf32 = False
    a, b = torch.randn(512,512), torch.randn(512,512)
    expected_cpu = a @ b
    ga, gb = a.cuda(), b.cuda()
    result = ga @ gb
    max_error = (result.cpu()-expected_cpu).abs().max().item()
    report['max_absolute_error'] = max_error
    if not torch.allclose(result.cpu(), expected_cpu, atol=0.0002, rtol=0.0002):
        raise RuntimeError('CPU/GPU computation mismatch')
    report['checks'].append('CPU/GPU matrix comparison passed')
    a = torch.randn(1536,1536,device='cuda')
    b = torch.randn(1536,1536,device='cuda')
    baseline = a @ b
    iterations = 0
    deadline = time.monotonic()+40
    next_sample = time.monotonic()
    while time.monotonic() < deadline:
        result = a @ b
        torch.cuda.synchronize()
        iterations += 1
        if iterations % 25 == 0 and not torch.equal(result,baseline):
            raise RuntimeError('Repeated GPU computation mismatch')
        if time.monotonic() >= next_sample:
            telemetry()
            next_sample = time.monotonic()+5
        time.sleep(0.01)
    telemetry()
    report['iterations'] = iterations
    report['checks'].append('40-second repeated computation check passed')
    report['status'] = 'passed'
except Exception as error:
    report['status'] = 'failed_or_stopped'
    report['error'] = str(error)
finally:
    report['elapsed_seconds'] = round(time.monotonic()-started,1)
    Path('tests/.artifacts').mkdir(exist_ok=True)
    Path('tests/.artifacts/gpu-health.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report),flush=True)
