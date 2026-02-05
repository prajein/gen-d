# Research Alignment: Gen-D

## Academic Context

This project is developed as a final-year academic project exploring the intersection of:

- **Software evolution** — How codebases change over time
- **Documentation maintenance** — Keeping docs synchronized with code
- **Program analysis** — Static extraction of semantic information
- **Developer tooling** — Building practical, usable systems

## Research Questions

### Primary Question

> How can we automatically detect when documentation becomes semantically inconsistent with the code it describes?

### Secondary Questions

1. What hashing strategy best captures "semantic equivalence" for documentation purposes?
2. How effective is function-level granularity for drift detection?
3. What is the relationship between call graph structure and documentation staleness propagation?
4. How can drift detection integrate into existing developer workflows?

## Theoretical Framework

### Semantic Drift

**Definition**: The gradual divergence between code behavior and its documentation over successive changes.

**Formal Model**:
```
Let C(t) = code state at time t
Let D(t) = documentation state at time t
Let S(x) = semantic hash function

Drift exists when:
  S(C(t₁)) ≠ S(C(t₀)) AND D(t₁) = D(t₀)
```

### Hash Stability

A semantic hash function S is **stable** if:
```
∀ c₁, c₂ : behavior(c₁) = behavior(c₂) → S(c₁) = S(c₂)
```

In practice, we approximate this by hashing normalized AST structure.

### Graph Representation

The codebase is modeled as a directed graph G = (V, E) where:
- V = set of functions/methods
- E = set of call relationships
- Each v ∈ V has attributes: semantic_hash, doc_hash, drift_status

## Module-Level Research Mapping

| Module | Input | Transformation | Output | Limitation |
|--------|-------|----------------|--------|------------|
| Parser | Source files | AST extraction | Function nodes | Dynamic code not captured |
| Hash | CST nodes | Normalization + SHA-256 | Semantic hash | Semantic equivalence is approximated |
| Graph | Nodes + calls | Graph construction | NetworkX DiGraph | Indirect calls not resolved |
| Drift | Current + stored hashes | Comparison | Drift status | Depends on hash quality |
| Storage | Graph snapshots | Serialization | SQLite records | Point-in-time only |

## Limitations (Explicitly Stated)

### Static Analysis Bounds

- **Dynamic dispatch**: Method calls through variables cannot be fully resolved
- **Metaprogramming**: `exec`, `eval`, decorators may hide behavior
- **External calls**: Library interactions are opaque

### Hash Approximation

- Semantic equivalence is undecidable in general
- Our hash approximates by normalizing AST structure
- False positives (hash differs but behavior same) possible for complex refactors
- False negatives (hash same but behavior differs) unlikely but possible with pathological code

### Scope Boundaries

- Python-only (no multi-language support)
- Function-level granularity (not statement-level)
- Single-project analysis (no cross-repo dependencies)

## Evaluation Criteria

### Correctness

- **Precision**: Of nodes marked STALE, what percentage truly have outdated docs?
- **Recall**: Of nodes with outdated docs, what percentage are detected?

### Usability

- Time to scan a codebase
- Clarity of drift reports
- Integration with developer workflow

### Scalability

- Performance on codebases of varying sizes
- Memory usage for large graphs

## Related Work

| System | Approach | Limitation |
|--------|----------|------------|
| Sphinx | Static doc generation | No drift detection |
| pydoc | Runtime introspection | No historical comparison |
| Doxygen | Comment extraction | No semantic analysis |
| Sourcegraph | Code intelligence | Focus on navigation, not docs |

Gen-D differs by:
1. Modeling code as a semantic graph
2. Computing logic-aware hashes
3. Detecting drift between states
4. Targeting documentation maintenance specifically

## Future Research Directions

1. **LLM-assisted regeneration**: Use drift context to prompt documentation updates
2. **Propagation analysis**: How does drift in one function affect callers?
3. **Temporal patterns**: Do certain code patterns correlate with faster drift?
4. **Cross-project analysis**: Shared library documentation consistency
5. **Quality scoring**: Beyond drift, measuring documentation completeness

## Contribution to Knowledge

This project contributes:

1. **A practical system** for drift detection in Python codebases
2. **A semantic hashing approach** for comparing code behavior
3. **An evaluation framework** for documentation maintenance tools
4. **Open-source infrastructure** for future research
