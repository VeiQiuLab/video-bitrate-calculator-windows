# Initialize relocated Tcl in the frozen process before the existing GUI starts.
from tk_runtime import prepare_tk
prepare_tk()

# Test-only mode: exercise the existing entrypoint's actual Tk instance and
# terminate normally, avoiding external process-tree termination permissions.
import sys
if '--archive-smoke-test' in sys.argv:
    import json
    from pathlib import Path
    import tkinter as tk
    report = Path(sys.argv[sys.argv.index('--report') + 1])
    def smoke(self, *args, **kwargs):
        result = {'ok': False, 'synthetic_inputs_only': True,
                  'manual_gui_acceptance': False}
        code = 1
        try:
            self.update()
            assert self.current.video_kbps == 2189
            assert len(self.table.get_children()) == 4
            self.vars['duration'].set('0')
            self.recalculate()
            assert self.current is None
            self.vars['duration'].set('9:38')
            self.recalculate()
            assert self.current.video_kbps == 2189
            result['ok'] = True
            result['checks'] = ['actual Tk instance', 'default 2189 kbps',
                                'four codecs', 'invalid input clears result',
                                'valid input recovers']
            code = 0
        except Exception as exc:
            result['error'] = type(exc).__name__ + ': ' + str(exc)
        finally:
            self.destroy()
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        raise SystemExit(code)
    tk.Misc.mainloop = smoke
