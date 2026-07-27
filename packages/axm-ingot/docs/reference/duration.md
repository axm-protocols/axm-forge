# `axm_ingot.duration`

Canonical stdlib-only formatter for millisecond durations. Several AXM surfaces
(gate diagnostics, session summaries, CLI reports) each rolled their own
milliseconds-to-human conversion, so `1500` surfaced variously as `"1.5s"`,
`"1500ms"` or `datetime.timedelta`'s `"0:00:01.500000"`. This single shared helper
removes the drift.

## `format_duration`

```python
format_duration(millis: float) -> str
```

Render a millisecond duration as a short human string. Sub-second values render
in integer milliseconds; the second, minute and hour bands render in their own
unit, rounded (not truncated) to at most one decimal. Negative, non-numeric or
non-finite input returns the fallback `"n/a"` without raising.

| Parameter | Type | Description |
|---|---|---|
| `millis` | `float` | The duration in milliseconds. |

**Returns** — `str`, the short human duration, or `"n/a"` for invalid input.

```python
>>> format_duration(450)
'450ms'
>>> format_duration(1500)
'1.5s'
>>> format_duration(90000)
'1.5min'
>>> format_duration(5400000)
'1.5h'
>>> format_duration(-5)
'n/a'
```
