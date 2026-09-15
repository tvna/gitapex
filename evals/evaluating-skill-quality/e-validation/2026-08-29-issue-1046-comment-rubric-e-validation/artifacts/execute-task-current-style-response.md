def near_ratio(text: str, entries: list) -> float:
    """Return the fraction of ``output_contains_near``-shaped entries satisfied against ``text``.

    Each item in ``entries`` is a mapping like ``{"all": [...], "window": int}``,
    the same shape ``score`` reads from an assertion set's ``output_contains_near``
    list (see this module's docstring for what "near" means). Per-entry
    satisfaction is delegated to this module's own ``_near_satisfied`` helper,
    so the span/window/blank-line semantics stay identical to the ones ``score``
    uses -- this function does not re-derive them. Returns a float in ``[0, 1]``.
    Raises ``ValueError`` when ``entries`` is empty, since a fixture with
    nothing to check cannot produce a ratio.
    """
    if not entries:
        raise ValueError("entries must not be empty")
    return sum(_near_satisfied(text, entry) for entry in entries) / len(entries)
