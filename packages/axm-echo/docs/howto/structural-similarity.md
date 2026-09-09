# Compare structural similarity

Use these library helpers when you already have Python function ASTs and
want a cheap comparison of statement shapes. This is separate from the
docstring-based `echo_code` and `echo_check` tools.

```python
import ast

from axm_echo import jaccard_similarity, statement_set

left = ast.parse("def first(x):\n    return x + 1\n").body[0]
right = ast.parse("def second(y):\n    return y + 99\n").body[0]
assert isinstance(left, ast.FunctionDef)
assert isinstance(right, ast.FunctionDef)

score = jaccard_similarity(statement_set(left), statement_set(right))
assert score == 1.0
```

The functions deliberately compute different values. Their normalized shapes
match because constants and `Name` identifiers are replaced. A score of
1.0 is therefore **not** semantic equivalence.

`statement_set()` flattens supported compound statement bodies and returns
a `frozenset[str]`; order and repetition are lost. The flattening includes
if/loop branches, with bodies and ordinary try handlers/finally blocks.
It does not uniformly flatten every Python construct: `match` and
`try*` are not special-cased. Attribute names and function argument
declarations are not all erased by the identifier normalization.

For a single statement, `normalize_dump(stmt)` returns a normalized string
or `None` if dumping fails. `flatten_body(body)` exposes the flattening
step when needed. `jaccard_similarity(a, b)` returns intersection/union:
two empty sets score 1.0, exactly one empty set scores 0.0.

These helpers use the standard-library AST and do not load torch. Importing
the package still loads its normal Python dependencies; this is not a
separate dependency-free installation.

See [Python API](../reference/api/index.md) for signatures.
