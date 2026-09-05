#!/bin/bash

# Reference solution: the expected classification verdict.
# A=Portable (all four conditions clear); B=Mixed-via-bundled-convention
# (only repo-specific content in a disclosed replace-on-vendoring file that
# a procedure step reads); C=Repository-scoped (two real sibling-skill
# dependencies = fan-out, trigger 2).
cat > /app/verdict.json << 'EOF'
{"case_a": "Portable", "case_b": "Mixed-via-bundled-convention", "case_c": "Repository-scoped"}
EOF