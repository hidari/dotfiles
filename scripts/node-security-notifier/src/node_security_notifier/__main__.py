"""python -m node_security_notifier のエントリポイント。"""

from __future__ import annotations

import sys

from node_security_notifier.cli import main

if __name__ == "__main__":
    sys.exit(main())
