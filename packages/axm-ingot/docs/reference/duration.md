# `axm_ingot.duration`

Canonical stdlib-only formatter for millisecond durations. Several AXM surfaces
(gate diagnostics, session summaries, CLI reports) each rolled their own
milliseconds-to-human conversion, so `1500` surfaced variously as `"1.5s"`,
`"1500ms"` or `datetime.timedelta`'s `"0:00:01.500000"`. This single shared helper
removes the drift.

## `format_duration`

```text
format_duration(millis: float) -> str
```

Render a millisecond duration as a short human string. Sub-second values render
in integer milliseconds; the second, minute and hour bands render in their own
unit, rounded (not truncated) to at most one decimal. Input is converted with `float()`. Negative or non-finite values and conversion
`TypeError`/`ValueError` return `"n/a"`. Other exceptions, including overflow
converting extremely large integers or custom conversion errors, can escape.

| Parameter | Type | Description |
|---|---|---|
| `millis` | `float` | The duration in milliseconds. |

**Returns** — `str`, the short human duration, or `"n/a"` for invalid input.

```python
>>> from axm_ingot import format_duration
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

## Band boundaries

Bands are selected before rounding: below 1000ms uses integer truncation;
1000–59999…ms uses seconds; 60000–3599999…ms uses minutes; 3600000ms and above
uses hours. Thus `999.9` → `"999ms"`, `1000` → `"1.0s"` and `59999` →
`"60.0s"`, rather than moving to the minute band. Numeric strings and booleans
are accepted by the current float conversion even though the annotated input
is `float`. No locale or day unit is applied.
