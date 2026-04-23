"""`python -m backup_tool` / `backup` エントリポイント。"""

from __future__ import annotations

import sys

from backup_tool.cli import main

if __name__ == "__main__":
    sys.exit(main())
