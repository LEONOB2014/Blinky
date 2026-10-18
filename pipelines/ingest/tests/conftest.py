import sys
from pathlib import Path

# pipelines/ingest is not a package; make its modules importable from these tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
