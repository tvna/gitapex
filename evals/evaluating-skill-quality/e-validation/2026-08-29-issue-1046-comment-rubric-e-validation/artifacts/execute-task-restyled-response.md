def near_ratio(text: str, entries: list) -> float:
    """Return the fraction of ``output_contains_near``-shaped entries satisfied
    against ``text``, as a float in ``[0, 1]``.

    Each entry in ``entries`` is a mapping like ``{"all": [...], "window": int}``,
    with the same shape and semantics as one ``output_contains_near`` assertion
    (see this module's docstring and ``_near_satisfied``): satisfied iff every
    listed substring's first occurrence falls within ``window`` characters
    (default 400) of every other, with no blank line (``"\n\n"``) between the
    occurrences. Per-entry satisfaction is delegated to this module's existing
    ``_near_satisfied`` helper rather than re-derived here.

    Raises ``ValueError`` when ``entries`` is empty, since a ratio over zero
    entries is undefined.
    """
    if not entries:
        raise ValueError("entries must not be empty")
    return sum(_near_satisfied(text, entry) for entry in entries) / len(entries)
