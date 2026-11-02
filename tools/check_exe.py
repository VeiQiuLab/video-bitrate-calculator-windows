"""Bounded automatic Tk check; this is not manual GUI acceptance."""
from pathlib import Path
import json,subprocess
root=Path(__file__).resolve().parents[1]
exe=root/'dist/VideoBitrateCalculator.exe'
report=root/'.build/checks/exe-selftest.json'
report.parent.mkdir(parents=True,exist_ok=True)
report.unlink(missing_ok=True)
subprocess.run([str(exe),'--archive-smoke-test','--report',str(report)],check=True,timeout=45)
result=json.loads(report.read_text(encoding='utf-8'))
assert result['ok'] is True,result
print('EXE self-test PASS: '+str(len(result['checks']))+' automatic Tk checks; manual acceptance not performed')
