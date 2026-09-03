from __future__ import annotations

import keyring

SESSION_PATH = "~/.probe_pkg/credentials.json"
user = "probe"
CREDENTIAL = keyring.get_password("probe_pkg-credentials", user)
