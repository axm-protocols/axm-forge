# Gate CI and publish a badge

Use the machine payload for automation. The human text can change and is not
a delimiter-based protocol. Do not mask an audit tool error with `|| true`.

## Check the quality verdict

In a checkout with its target environment and the generic `axm` CLI ready:

```bash
axm audit . --json-output > audit.json
jq -e '(.failed | length) == 0 and (.score | type) == "number"' audit.json
```

This policy requires no failed checks and a calculable score. Adapt the
minimum score to your policy without dropping the failure check. CI must
also verify the required categories/tools were available: a number alone
does not prove complete measurement.

For pytest evidence:

```bash
axm audit_test . --include-cases --json-output > tests.json
jq -e '.verdict == true' tests.json
```

Use fail-fast shell execution (`set -e` in a standalone script) so the
tool command must succeed before jq reads its output.

## Generate a badge artifact

After successfully producing `audit.json`, this command creates a
Shields endpoint JSON artifact. Failed or unavailable quality is red even
when the numeric grade would be A.

```bash
mkdir -p badges
jq '{
  schemaVersion: 1,
  label: "axm-audit",
  message: (if .score == null then "N/A" else (.score | tostring) + "/100" end),
  color: (if (.failed | length) > 0 or .score == null then "red"
          elif .score >= 90 then "brightgreen"
          elif .score >= 80 then "green"
          elif .score >= 60 then "yellow" else "red" end)
}' audit.json > badges/axm-audit.json
```

Publishing is a separate repository decision. Serve the JSON from a stable
public URL and use that URL as the Shields endpoint; badge generation itself
does not require write credentials or a push to a branch.
The workspace's existing quality workflow may already own publication.

If adding a logo, omit `logoSvg` when the fetch fails or is empty. An empty
logo can invalidate an otherwise valid badge.

See [scoring](../explanation/scoring.md) and [tool errors](../reference/cli.md#errors-and-transport).
