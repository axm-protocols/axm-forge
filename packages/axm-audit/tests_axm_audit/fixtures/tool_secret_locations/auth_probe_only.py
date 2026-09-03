from __future__ import annotations

import subprocess

STATUS = subprocess.run(
    ["gh", "auth", "status"],  # noqa: S607
    check=False,
)
