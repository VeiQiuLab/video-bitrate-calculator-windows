"""Actual Tk widgets with synthetic inputs; dialogs/clipboard payloads stubbed."""
from pathlib import Path
import runpy, sys, tempfile
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from tk_runtime import prepare_tk
prepare_tk()
ns=runpy.run_path(str(root/'bitrate_gui.pyw'),run_name='archive_gui_test')
app=ns['VideoBitrateCalculator']()
try:
 app.withdraw();app.update()
 assert app.current.video_kbps==2189
 assert len(app.table.get_children())==4
 for codec in ns['CODECS']:
  app.table.selection_set(codec);app.on_select(None)
  assert codec in app.preview.get('1.0','end')
  with patch.object(app,'_copy') as copy:
   app.copy_selected();assert '2189 Kbps' in copy.call_args.args[0]
 with tempfile.TemporaryDirectory(prefix='bitrate-gui-') as folder:
  exported=Path(folder)/'export.txt'
  with patch.object(ns['filedialog'],'asksaveasfilename',return_value=str(exported)):
   app.export_txt()
  assert all(c in exported.read_text(encoding='utf-8-sig') for c in ns['CODECS'])
 app.vars['duration'].set('0');app.recalculate();assert app.current is None
 app.vars['duration'].set('9:38');app.recalculate();assert app.current.video_kbps==2189
 print('PASS: actual Tk controls, four codecs, mocked copy payloads, isolated TXT export, invalid input')
finally:
 app.destroy()
