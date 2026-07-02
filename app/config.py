"""Environment-driven settings. No external config framework needed."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATA_MODE = os.environ.get("DATA_MODE", "auto").lower()  # auto | live | sample
COMTRADE_API_KEY = os.environ.get("COMTRADE_API_KEY") or None
DB_PATH = Path(os.environ.get("TRADE_DB_PATH") or ROOT / "data" / "trade.sqlite")
SAMPLE_DATA_PATH = ROOT / "data" / "sample" / "sample_trade.json"
STATIC_DIR = ROOT / "static"
PORT = int(os.environ.get("PORT", "8000"))

YEARS = list(range(2018, 2025))
CACHE_TTL_SECONDS = 30 * 24 * 3600  # annual data barely moves
