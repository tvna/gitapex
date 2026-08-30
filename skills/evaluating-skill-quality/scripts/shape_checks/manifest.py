"""``spec_of``: the one shared accessor for the metadata/gitapex.yaml
sidecar's ``spec`` mapping (issue #758).

Before this migration this module also housed a ~1,150-line hand-rolled,
indentation-driven reader for the YAML subset the sidecar is specified to
use (``_parse_manifest``/``ManifestParse``). That reader is retired
entirely: the sidecar is now parsed with ``yaml.safe_load`` (a real YAML
parser) in ``gitapex_check_skill_shape.check_shape``, and its structural
shape is validated against ``skill-metadata.schema.json`` via
``jsonschema.Draft202012Validator`` (``shape_checks.schema``) -- the
schema is the sole source of truth for the sidecar's shape, eliminating
the class of drift between a hand-rolled reader and the schema it was
meant to mirror.
"""

from __future__ import annotations


def spec_of(manifest: dict[str, object]) -> dict[str, object] | None:
    """Return ``manifest["spec"]`` if present and a mapping, else None.

    A malformed sidecar can write ``spec:`` as a scalar or list rather than
    a mapping; every consumer that only cares about "does this sidecar have
    a real spec mapping" needs the same isinstance guard around
    ``manifest.get("spec")``; sharing this guard avoids the pattern
    regressing independently at each call site. Callers outside this
    module (e.g. tests/test_gitapex_skill_metadata_sidecar.py) should use
    this instead of inlining ``manifest.get("spec")`` themselves.
    """
    spec = manifest.get("spec")
    return spec if isinstance(spec, dict) else None
