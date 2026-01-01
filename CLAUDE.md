# Research Features Implementation

Plan: `~/.claude/plans/giraf-research-features.md`
Spec: `RESEARCH_FEATURES_SPEC.md`

## Current Status

| Phase | Status |
|-------|--------|
| 1. Core Infrastructure | ✅ Done |
| 2. Query Logging | ✅ Done |
| 3. Guardrails System | ✅ Done |
| 4. Knowledge Capture | ✅ Done |
| 5. Resilience Testing | ✅ Done |
| 6. Cross-Disciplinary | ❌ Next |
| 7. Integration & Docs | ⚠️ Partial |

## Quick Commands

```bash
# Run tests
pytest

# Run specific phase tests
pytest tests/test_guardrails*.py -v

# Check feature status
GIRAF_GUARDRAILS_ENABLED=true python -c "from girafmcp.core.features import *; print([f'{s.feature.name}: {s.enabled}' for s in FeatureRegistry.get_all_states()])"
```
