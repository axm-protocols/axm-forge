# Built-in tools

These are registered by the MCP server even without optional tool packages.
Their presence in `list_tools` is not proof that their dependencies are
installed. They are not exposed as `axm.tools` entry points by axm-mcp.

## verify

Signature: `verify(path=".")`. It calls discovered `audit` and
`init_check`, then optionally enriches eligible audit failures with
`ast_impact`. It returns text through MCP, with structured
`audit`/`governance` sections available on the underlying ToolResult.

Absent provider → null section; failed provider → error section.
Completed aggregation returns outer success even with quality findings.
See [Use verify](../howto/verify.md) for interpretation and operational effects.

## web_fetch

Signature: `web_fetch(url, mode="auto")`.

| Mode | Backend behavior |
|---|---|
| `auto` | Exactly the basic route; no automatic escalation |
| `basic` | Scrapling Fetcher.get on a worker thread |
| `dynamic` | Scrapling DynamicFetcher.async_fetch |
| `stealth` | Scrapling StealthyFetcher.async_fetch |

Install the optional backend in the same server environment. The `web`
extra declares `scrapling`, but the fetcher import requires the backend's
fetcher dependencies. The tool's missing-backend diagnostic recommends:

```bash
uv pip install --python /absolute/path/to/server-venv/bin/python "scrapling[fetchers]"
```

Browser modes additionally require the browser runtime expected by your
Scrapling installation. Neither `forge` nor `all` includes this extra.

MCP call parameters:

```json
{"name": "web_fetch", "arguments": {"url": "https://example.com", "mode": "basic"}}
```

On successful fetching, data contains `url`, `title`, `text`,
`status_code` (possibly null), and the requested `mode`.
Text is cut at 50,000 characters and then receives a truncation marker.
Success means a page object was processed, **not an HTTP 2xx check**:
inspect `status_code`. This tool returns extracted text, not a DOM or
Markdown conversion.

Missing backend and invalid mode return failures; fetching exceptions return
their error string plus URL/mode. The missing-backend check precedes mode
validation, so it can mask an invalid mode. It has no tool-level custom
timeout or retry parameter. Dynamic/stealth fetching is not a guarantee
of bypassing a site's protections.

Fetching sends a network request and can start a browser. Use it only for
URLs you intend the server to contact; this adapter does not implement a
network allowlist or SSRF boundary.

## list_tools

Call directly with `arguments={"kwargs": {}}`. The Python body has no
required named input, but MCP 1.30 exposes its `**kwargs` as a required
object; omitting it produces a schema validation error. It returns sorted text for
discovered tools plus built-in/meta-tool descriptions, including entries
not individually exposed by MCP `tools/list`. It does not execute each
tool to check health. The facade meta-tools are described in
[Facade and result contracts](facade.md).
