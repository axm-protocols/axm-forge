from __future__ import annotations

import keyring

user = "probe"
CREDENTIAL = keyring.get_password("Claude Code-credentials", user)
