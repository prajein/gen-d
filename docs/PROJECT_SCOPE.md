# Project Scope: Gen-D

## Problem Statement

Traditional documentation systems are **static and fragile**. As source code evolves, documentation becomes semantically stale, leading to:

- Incorrect explanations that mislead developers
- Confusion during onboarding and knowledge transfer
- Accumulated maintenance debt
- Erosion of trust in documentation

Existing tools generate documentation once and do not:
- Detect semantic drift between code and docs
- Model code as a navigable graph
- Provide localized context for regeneration

**This project addresses that gap.**

## Core Thesis

> **Documentation should be treated as a derived, living artifact that must evolve in lockstep with the semantic structure of code.**

Gen-D operationalizes this thesis by:

1. Modeling code as a **function-level dependency graph**
2. Computing **semantic hashes** of logic (excluding formatting and comments)
3. Detecting **drift** between code and its last-documented state
4. Exposing this information via a **CLI and API**
5. Enabling safe, atomic documentation regeneration

## Scope Boundaries

### In Scope

| Feature | Description |
|---------|-------------|
| Python parsing | LibCST-based function and method extraction |
| Semantic hashing | Logic-aware hashing that ignores formatting |
| Dependency graph | NetworkX-based function call graph |
| Drift detection | FRESH/STALE/UNDOCUMENTED classification |
| CLI interface | `scan`, `status`, `explain` commands |
| SQLite storage | Snapshot persistence for drift comparison |

### Out of Scope

| Feature | Rationale |
|---------|-----------|
| IDE plugins | Focus on CLI-first architecture |
| Multi-language support | Python-only for v1 |
| Automatic code rewriting | Developer-in-the-loop philosophy |
| Perfect call resolution | Static analysis has inherent limits |
| LibCST modifications | Use as dependency only |

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.10+ | Target ecosystem |
| Parsing | LibCST | Concrete syntax tree with position info |
| Graph | NetworkX | Mature, well-documented graph library |
| Persistence | SQLite | Zero-config, file-based storage |
| CLI | Typer + Rich | Modern CLI with beautiful output |
| File watching | watchdog | Cross-platform file monitoring |

## Success Criteria

1. A Python repository can be scanned successfully
2. Drift is detected correctly and consistently
3. Output is human-readable and actionable
4. Codebase is navigable by students and contributors
5. Architecture aligns with the research thesis

## Research Alignment

This system supports academic inquiry into:

- **Semantic drift**: How code semantics diverge from documentation over time
- **Graph representation**: Function-level dependency modeling
- **Automated maintenance**: Detecting which docs need regeneration
- **Developer workflow**: Human-in-the-loop verification

Every module should be explainable in academic terms:
- Input (what data enters)
- Transformation (what processing occurs)
- Output (what artifacts are produced)
- Limitations (what cannot be guaranteed)

## Extension Points

Future work may extend this system with:

- [ ] FastAPI server for web interface
- [ ] LLM integration for doc generation suggestions
- [ ] Git integration for commit-based drift tracking
- [ ] Configurable hash normalization rules
- [ ] Cross-module dependency analysis
- [ ] Documentation quality scoring

## Non-Goals (Explicit)

To maintain focus, this project will **not**:

- Build an IDE plugin or editor integration
- Modify or fork LibCST internals
- Promise support for languages other than Python
- Perform whole-program formal verification
- Aim for perfect static call resolution
- Auto-rewrite code without explicit user action

This is a **developer-in-the-loop system**, not an autonomous agent.
