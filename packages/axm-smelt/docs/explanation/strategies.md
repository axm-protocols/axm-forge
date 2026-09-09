# Strategy Behavior and Fidelity

Strategy categories describe intent, not a losslessness guarantee. Each
candidate is accepted only if it reduces tokens, or shortens text at equal
token count. Examples here explain candidate transformations; the pipeline
may discard them. [Use strategies](../howto/strategies.md) for runnable calls.

## minify

**Category: whitespace.** Compact JSON serialization uses sorted keys,
compact separators and unescaped Unicode. It preserves ordinary JSON values
after parsing, but not bytes, original key order, number spelling or duplicate
object keys.

For YAML, it uses PyYAML parse/dump in flow style. A **full-line** `#` comment
prevents this conversion, but inline comments are not protected and can be
removed. Even the skip path begins from trimmed text. YAML presentation,
anchors and scalar spelling are not a preservation contract.

For XML, regular expressions remove inter-tag whitespace and spaces/tabs around
text nodes, while protecting CDATA sections. This can change significant text
and mixed-content spacing; there is no XML parser or `xml:space` handling.

Consequently the default `safe` preset is not a general lossless transform.
For example, it can produce:

```text
Input:  <root>  hello  <child>  world  </child>  </root>
Output: <root>hello<child>world</child></root>
```

Choose it only when these representation changes are acceptable.

## drop_nulls

**Category: structural. Lossy.** Recursively remove dictionary entries and list
elements equal to `None`, `""`, `[]`, or `{}`, including containers that
become empty after cleaning. Zero and false remain. List positions can shift,
and missing fields are not equivalent to null for many consumers.

Use it when empty values carry no information in the application.

## flatten

**Category: structural. Changes schema; collisions can lose values.**
Collapse single-child wrapper dictionaries by joining path segments with dots.
The traversal also visits values within larger dictionaries and lists; a
multi-key parent does not prevent eligible child wrappers from flattening.

```text
Input:  {"user": {"profile": {"name": "Alice"}}}
Output: {"user.profile.name":"Alice"}
```

There is no escaping or collision check for literal dotted keys. For example,
`{"a":{"b":1},"a.b":2}` can become `{"a.b":2}`, losing the nested value.
Use only where key paths are controlled and the changed schema is expected.
The registered strategy uses unlimited depth; the public pipeline exposes
no max-depth option.

## tabular

**Category: structural. Lossy.** A nonempty list of dictionaries becomes
a pipe-separated header and rows. Keys are collected in first-seen order;
records need not have identical keys. Arrays nested inside dictionaries can
become table strings too. Lists containing non-dictionary elements are not
converted into a table.

```text
Input:  [{"name":"Alice","age":30},{"name":"Bob","age":25}]
Output:
name|age
Alice|30
Bob|25
```

Missing keys become empty cells. Null, booleans and numbers lose their
distinction from string spellings; nested values are serialized. The output is
not a typed round-trip interchange format, nor a standard Markdown table.
Earlier accepted transformations can affect column order. Use it for reading
records in context, not for exact reconstruction.

## dedup_values_with_refs

**Category: structural. Reconstructable with its envelope, not schema-preserving.**

Repeated string values of at least 20 characters, occurring at least twice,
are candidates for aliases. Their order uses character length times occurrence
count, descending; this ranking is not itself a token-savings calculation.
The pipeline's token guard decides whether the complete envelope is worthwhile.

The output has `_refs` (alias → original string) and `_data` (transformed
payload). A root dictionary already containing either reserved key is skipped.
There is no public inverse function; a consumer must reconstruct string values
under `_data` using the supplied mapping.

The default prefix is `$R`. If any original string value begins with that
prefix, it escalates to `$$R`, then `$$$R`, and so on. Literal string values
therefore do not collide with generated aliases. Keys are not aliased.
Later strategies in a preset can further transform this envelope, so its
standalone reconstruction contract does not make the whole preset reversible.

Use for sufficiently long, repeated descriptions, URLs or other string values.
Two short eligible strings may not compensate for the envelope overhead.

## strip_quotes

**Category: cosmetic. Output is not standard JSON.** Remove quotes from keys
matching ASCII `[a-zA-Z_][\w.]*`: an initial letter/underscore, followed by
letters, digits, underscores or dots. The strategy requires the JSON format
label and works by regular expression.

```text
Input:  {"name":"Alice"}
Candidate: {name:"Alice"}
```

Use only for consumers explicitly accepting the representation. A dotted key
is not necessarily a valid identifier in another relaxed-JSON dialect.
Do not infer JSON validity from the report's retained input-format label.

## round_numbers

**Category: cosmetic. Lossy.** Round floats using Python's `round` with
two decimal places by default; integers remain unchanged. The registered
pipeline does not expose a precision argument. Earlier strategies can replace
numeric values with table strings, preventing later rounding.

Use for approximate context where precision is dispensable, not for downstream
calculations requiring the original values.

## collapse_whitespace

**Category: whitespace. Can change Markdown meaning.** Collapse runs of three
or more newline characters to two and strip trailing spaces/tabs. JSON, YAML,
XML, TOML and CSV labels are skipped.

The protection pattern recognizes matched runs of at least three backticks;
it is not a complete Markdown parser. Tilde fences, indented code and unmatched
fences are not protected. Removing two trailing spaces can remove a Markdown
hard line break. Newlines around protected blocks are also normalized, and
adjacent backtick blocks can be joined at their delimiters.

For example, a closing three-backtick fence and the next opening fence can
become one six-backtick run, changing the document structure. Preserve the
original when code-fence boundaries or Markdown rendering matter.

This strategy is included in every preset, including `safe`.

## compact_tables

**Category: whitespace.** For a Markdown-classified document, strip padding
from pipe-delimited cells on matching lines. Recognized backtick-fence lines
are skipped, with the same limited fence recognizer described above.

It operates on lines and pipe separators rather than a full Markdown table
syntax tree. Review inline code and complex cell content instead of treating
it as a general rendering-preserving formatter.

## strip_html_comments

**Category: cosmetic. Lossy.** Remove `<!-- ... -->` comments from Markdown
and text, clean up adjacent whitespace and collapse long blank-line runs.
Recognized backtick blocks are protected; tilde/indented/unmatched code is not.

Use when those comments are deliberately expendable. Removal is not a
sensitive-data scrubber: secrets elsewhere in the text remain.
