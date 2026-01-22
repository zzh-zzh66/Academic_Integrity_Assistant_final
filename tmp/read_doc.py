import sys
import os
sys.path.insert(0, os.getenv('COZE_WORKSPACE_PATH'))
sys.path.insert(0, os.path.join(os.getenv('COZE_WORKSPACE_PATH'), 'src'))

from utils.file.file import File, FileOps

file = File(url='/tmp/Academic_Integrity_Assistant.docx', file_type='document')
content = FileOps.extract_text(file)
print(content)
