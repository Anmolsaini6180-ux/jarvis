import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from actions import file_controller as f
from core import undo
class BaselineRisks(unittest.TestCase):
 def test_rename_boundary(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'allowed';root.mkdir();(root/'a').write_text('source')
   with patch.object(f,'_SAFE_ROOTS',[root]): f.rename_file(str(root/'a'),new_name=str(Path(d)/'escape'))
   self.assertFalse((Path(d)/'escape').exists())
 def test_copy_collision(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'a').write_text('source');(root/'b').write_text('original')
   with patch.object(f,'_SAFE_ROOTS',[root]): f.copy_file(str(root/'a'),destination=str(root/'b'))
   self.assertEqual((root/'b').read_text(),'original')
 def test_undo_conflict(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p=root/'a';p.write_text('original');undo.clear()
   with patch.object(f,'_SAFE_ROOTS',[root]):
    f.write_file(str(p),content='assistant');p.write_text('newer');undo.undo_last()
   self.assertEqual(p.read_text(),'newer')
if __name__=='__main__':unittest.main()
