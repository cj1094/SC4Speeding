"""Launch the example-based ordinance build (requires sc4@0.2.24)."""
from pathlib import Path
import subprocess
subprocess.run(['node',str(Path(__file__).with_suffix('.mjs'))],check=True)
