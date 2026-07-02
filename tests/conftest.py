import os
import sys
from pathlib import Path

os.environ["DATA_MODE"] = "sample"
os.environ["TRADE_DB_PATH"] = ":memory:"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
