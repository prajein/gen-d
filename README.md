# gen-d

**A Living Documentation Engine for Detecting Semantic Drift in Python Codebases**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Gen-D is a developer-in-the-loop system that treats documentation as a **derived, living artifact** that must evolve in lockstep with code semantics.

Traditional documentation tools generate docs once and never detect when they become stale. Gen-D addresses this by:

1. **Modeling code as a graph** — Functions and methods become nodes; calls become edges
2. **Computing semantic hashes** — Logic-aware hashing that ignores formatting and comments
3. **Detecting drift** — Identifying when code changes but documentation doesn't
4. **Enabling targeted regeneration** — Pinpointing exactly which docs need updates

## Installation

```bash
# Clone the repository
git clone https://github.com/prajein/gen-d.git
cd gen-d

# Install in development mode
pip install -e ".[dev]"
```

## Quick Start

```bash
# Scan a Python project
gdg scan ./your-project

# Check documentation status
gdg status

# Explain drift for a specific function
gdg explain your_module:function_name
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `gdg scan <path>` | Parse a Python codebase and build the dependency graph |
| `gdg status` | Display drift summary: stale, fresh, and undocumented functions |
| `gdg explain <id>` | Show detailed drift information for a specific function |

## Architecture

```
gen-d/
├── engine/
│   ├── parser/     # LibCST-based code extraction
│   ├── hash/       # Semantic hashing logic
│   ├── graph/      # NetworkX graph construction
│   ├── drift/      # Drift detection algorithms
│   └── storage/    # SQLite persistence
├── cli/            # Typer + Rich CLI interface
├── docs/           # Project documentation
└── tests/          # Test suite
```

## Core Concepts

### Semantic Hashing

Unlike textual hashing, semantic hashes:
- Ignore whitespace and formatting
- Ignore comments and docstrings
- Remain stable across non-behavioral refactors

### Drift States

| State | Meaning |
|-------|---------|
| `FRESH` | Documentation matches current code semantics |
| `STALE` | Code logic changed but docstring didn't |
| `UNDOCUMENTED` | No docstring exists |

## Development

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=engine --cov-report=term-missing

# Format code
black engine/ cli/ tests/

# Lint
ruff check engine/ cli/ tests/
```

## Research Context

This project supports academic research on:
- Semantic drift in evolving software systems
- Graph-based code representation
- Automated documentation maintenance
- Developer-in-the-loop regeneration

## License

MIT License — see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! This project is designed for student contributions with clear extension points and comprehensive documentation.
