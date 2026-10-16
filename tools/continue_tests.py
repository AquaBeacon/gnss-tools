import time,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
deadline=time.monotonic()+600
while not (ROOT/'reports/01_Basic/test_events.json').exists():
    if time.monotonic()>deadline:raise TimeoutError('Initial receiver test did not complete')
    time.sleep(1)
for args in [
    ['--rates-only','--lean','--session','rates_lean'],
    ['--rtk-only','--lean','--session','nearby','--host','geortk.jp','--mount','btf_nishiyamacho3'],
]:
    subprocess.run([sys.executable,str(ROOT/'tools/verify_receiver.py'),'COM7',*args],cwd=ROOT,check=True)
