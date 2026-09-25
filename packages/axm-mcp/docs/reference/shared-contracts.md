# Shared write contracts

Streamable HTTP is a transport. `dedicated` and `shared` are separate
serving policies; an HTTP process can run either.

## Start the shared policy

```bash
axm-mcp serve --shared --host 127.0.0.1 --port 9427
# or: AXM_MCP_SERVE_MODE=shared axm-mcp serve --host 127.0.0.1 --port 9427
```

Keep `AXM_MCP_FACADE` enabled. The mode resolves, highest first: the explicit
`--shared / --no-shared` option, then `AXM_MCP_SERVE_MODE`, then `[mcp]
serve_mode` in `$AXM_HOME/config.toml`, then `dedicated`. `serve` prints the
resolved mode on stderr at startup (`axm-mcp: serve mode shared`), and
`GET /health` reports it:

```json
{"status": "ok", "tools_count": 7, "serve_mode": "shared", "write_contracts_enforced": true}
```

`write_contracts_enforced` is `true` only in shared mode.

An MCP client first establishes a session and then carries its
`mcp-session-id` on requests. To bind a contract it additionally sends
`X-AXM-Write-Contract` containing a JSON object, for example:

```json
{
  "execution_root": "/absolute/path/to/checkout",
  "allowed_prefixes": ["/absolute/path/to/checkout"],
  "markdown_only_prefixes": []
}
```

The header's value is that JSON serialized onto one line. This is a header
payload, not an MCP tool argument. Use the actual session ID returned by the
MCP transport, not a made-up identity.

## Binding and enforcement

The shared HTTP middleware reads both headers and binds a normalized
contract to the supplied identity before tool dispatch. A subsequent valid
declaration for that identity **replaces** its prior contract. Missing headers
do not create a binding. Invalid declarations are ignored by the middleware;
an existing binding is not revoked by a malformed replacement.

Both catalog calls and direct hot-path calls resolve the contract at call
time. A session carrying a contract is restricted to that contract's perimeter.
An unbound session carries no contract and is therefore treated as the local
operator: wrapped reads and mutations execute without a write perimeter. The
wrapper applies this rule identically whether resolution returns `None` or raises
`UnboundSessionError`. The actual write decision is delegated to
`axm.tools.write_scope`; its coverage depends on the tool name and payload.

### Unscoped execution

`run_command` belongs to `UNSCOPED_EXECUTION_TOOLS`: its filesystem effects
cannot be inferred from its `command` payload. The common wrapper therefore
refuses it before consulting the ordinary write-scope decision when, and only
when, shared mode is active and the emitting session has a non-null contract.
The refusal is identical through `build_wrappers` and the facade's `axm_call`
route. A shared session without a bound contract remains the local operator and
can execute it; dedicated mode is unchanged.

## Scope of the guarantee

This is a cooperative write perimeter for trusted callers, **not
authentication or an operating-system sandbox**. The server does not verify
that a client is entitled to the prefixes it declares, and it does not sign
or authorize header declarations. A bound session cannot dispatch
`run_command`, but other tools may still produce subprocess effects that their
payload does not reveal. Read access, external services and unclassified
capabilities are not made safe merely by assigning a filesystem prefix. Keep
the service on a trusted boundary.

Current implementation limits:

- With `AXM_MCP_FACADE=0`, discovered tools are registered without the
  shared-mode resolver, while built-ins still receive it. Do not use
  facade-disabled mode when relying on per-session enforcement.
- A wrapper checks the incoming payload before unwrapping a nested
  `kwargs` dictionary. Use the documented flat argument shape; this
  machinery is not a security barrier for adversarial inputs.
- The registry stores contracts in memory. Restart loses bindings. Its
  `purge_expired(now)` method implements a default 3600-second TTL,
  but expiry is **not automatic on resolve**, and the server has no periodic
  purge wired here. Do not assume time alone revokes a session.
- Explicit release exists on the registry, but the end-session helper is not
  wired to automatic MCP session closure. Transport closure is not proof of
  registry removal.
- Dedicated mode falls back to the process's environment-backed AXM write
  contract and still propagates `UnboundSessionError` from an explicit resolver.
  Shared mode converts that error to the no-contract operator case. Neither mode
  fabricates or substitutes a default perimeter when no contract is in force.

[Concurrency](../explanation/architecture.md#concurrency) describes in-process
serialization, which is separate from authorization and atomic writes.
