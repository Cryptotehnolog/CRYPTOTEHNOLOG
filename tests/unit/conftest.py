# ==================== Unit Tests Configuration ====================
# This conftest.py is loaded BEFORE collecting tests in tests/unit/

import sys
from pathlib import Path

# Add src directory to Python path BEFORE any test imports
# This is required for pytest-xdist to find cryptotechnolog modules
_src_path = Path(__file__).parent.parent.parent / "src"
if str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

# Diagnostic output to verify sys.path is set correctly
print(f"[conftest] sys.path[0] = {sys.path[0]}")
print(f"[conftest] src_path = {_src_path}")
print(f"[conftest] cryptotechnolog in sys.modules = {'cryptotechnolog' in sys.modules}")

# Try to import cryptotechnolog.data to verify it works
try:
    import cryptotechnolog.data
    print(f"[conftest] Successfully imported cryptotechnolog.data from {cryptotechnolog.data.__file__}")
except Exception as e:
    print(f"[conftest] FAILED to import cryptotechnolog.data: {e}")
