# Witnesses

These validation contracts are distinct from tool results. The SDK supplies
types and helpers; it does not execute validators or enforce a gate.


A `WitnessRule` supplies `validate(content: str, **kwargs) -> WitnessResult`.
Unlike `ToolResult`, the result uses the boolean field `passed`.
Its optional `verdict` is routing information for a consumer, not a validated
enumeration or a scheduler action.

```python
from axm import ValidationFeedback, WitnessResult

feedback = ValidationFeedback(
    what="Title missing",
    why="The document requires a title",
    how="Add a level-one heading",
)
result = WitnessResult.failure(feedback, verdict="repair")
assert not result.passed
assert feedback.to_dict()["how"] == "Add a level-one heading"

accepted = WitnessResult.success(verdict="continue", metadata={"checked": 1})
assert accepted.passed
```

All three feedback strings (`what`, `why`, `how`) are required.
`to_dict()` returns those same three keys.
The helpers `success` and `failure` populate a result; they do not execute
a validator or constrain the caller's choice of verdict.

::: axm.witnesses.ValidationFeedback
    options:
      skip_local_inventory: true

::: axm.witnesses.WitnessResult
    options:
      skip_local_inventory: true

::: axm.witnesses.WitnessRule
    options:
      skip_local_inventory: true
