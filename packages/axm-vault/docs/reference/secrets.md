# Secrets

Helpers for wrapping credential values in a pydantic
[`SecretStr`](https://docs.pydantic.dev/latest/api/types/#pydantic.types.SecretStr)
and for scrubbing secrets out of arbitrary text (e.g. logs).

!!! warning "Reveal surface"
    A `SecretStr` never exposes its plaintext in `repr()`, `str()`, an
    f-string, or `model_dump()` / `model_dump_json()` — it always renders
    as `**********`. The plaintext is reachable **only** through an
    explicit `get_secret_value()` call, which is the single audited reveal
    surface.

## `as_secret`

```python
as_secret(value: str | SecretStr | None) -> SecretStr | None
```

Coerce a raw secret string into a `SecretStr`. `None` passes through
unchanged (for optional secrets), and an existing `SecretStr` is returned
as-is (idempotent).

```python
from axm_vault import as_secret

token = as_secret("s3cr3t")
repr(token)                 # "SecretStr('**********')" — no plaintext
token.get_secret_value()    # "s3cr3t"  (the only reveal surface)

as_secret(None)             # None
as_secret(token) is token   # True (idempotent)
```

A model field typed as `SecretStr` never leaks on dump:

```python
from pydantic import BaseModel, SecretStr
from axm_vault import as_secret

class Config(BaseModel):
    token: SecretStr

m = Config(token=as_secret("s3cr3t"))
m.model_dump()        # {"token": SecretStr('**********')}
m.model_dump_json()   # '{"token":"**********"}'
```

## `redact`

```python
redact(text: str, *secrets: str | SecretStr) -> str
```

Mask occurrences of known secret substrings in `text` for log scrubbing.
Each qualifying secret is replaced by `********` (the exported `MASK`
constant). A `SecretStr` argument is accepted and unwrapped via
`get_secret_value()`, so a redaction site can pass the live secret without
ever holding its plaintext itself.

The pass is hardened against two failure modes:

- **Longest-first** — secrets are masked in descending length order, so a
  short secret that is a *prefix* of a longer one can never mask only the
  prefix and leave the longer secret's tail exposed.
- **Minimum length** — secrets shorter than `MIN_REDACT_LEN` (4) — and empty
  ones — are ignored, since masking a tiny substring over-redacts the
  surrounding text without protecting anything.

```python
from pydantic import SecretStr
from axm_vault import redact

redact("auth=s3cr3t now", "s3cr3t")           # "auth=******** now"
redact("nothing to hide")                     # "nothing to hide"
redact("X=abcdef", "abc", "abcdef")           # "X=********"  (longest-first, no tail leak)
redact("auth=s3cr3t", SecretStr("s3cr3t"))    # "auth=********"  (SecretStr unwrapped)
```

!!! warning "Best-effort, not a security boundary"
    `redact` only masks the exact substrings it is given, in the casing it is
    given; it cannot catch transformed, encoded, or partial echoes. It is
    best-effort log scrubbing. The authoritative never-leak surface is
    `SecretStr` itself.

## `MASK`

The replacement string used by `redact`: `"********"`.
