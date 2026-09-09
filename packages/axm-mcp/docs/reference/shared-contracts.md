# Shared write contracts

Streamable HTTP is a transport. `dedicated` and `shared` are separate
serving policies; an HTTP process can run either.

## Start the shared policy

```bash
AXM_MCP_SERVE_MODE=shared axm-mcp serve --host 127.0.0.1 --port 9427
```

Keep `AXM_MCP_FACADE` enabled. The CLI's `--shared` flag currently refuses
startup; the environment or configuration-file policy is the working route.

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
time. An unbound session is refused by the wrapper **even for a read-only
wrapped tool**, because resolution happens before tool classification.
The unwrapped facade discovery tools and `list_tools` remain available for
finding contracts. The actual write decision is delegated to
`axm.tools.write_scope`; its coverage depends on the tool name and payload.

## Scope of the guarantee

This is a cooperative write perimeter for trusted callers, **not
authentication or an operating-system sandbox**. The server does not verify
that a client is entitled to the prefixes it declares, and it does not sign
or authorize header declarations. Read access, subprocess effects, external
services and unclassified tools are not made safe merely by assigning a
filesystem prefix. Keep the service on a trusted boundary.

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
  contract; without a contract it permits calls. A shared server never
  substitutes that default for a missing session contract on its armed paths.

[Concurrency](../explanation/architecture.md#concurrency) describes in-process
serialization, which is separate from authorization and atomic writes.
