from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from test_remote_server.server import mcp

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
