# Architecture: Gen-D

## System Overview

Gen-D is a pipeline-based system that transforms Python source code into a semantic dependency graph, then uses that graph to detect documentation drift.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Source    │────▶│   Parser    │────▶│   Hasher    │────▶│   Graph     │
│   Files     │     │  (LibCST)   │     │ (Semantic)  │     │ (NetworkX)  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                                                                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    CLI      │◀────│   Drift     │◀────│  Comparator │◀────│   Storage   │
│  (Output)   │     │  Detector   │     │             │     │  (SQLite)   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

## Module Responsibilities

### `engine/parser/` — Code Extraction

**Input**: Python source files  
**Output**: Raw function/method data with positions and docstrings

Responsibilities:
- Use LibCST to parse Python files
- Extract function and method definitions
- Collect class hierarchies
- Identify call sites for edge discovery

Key Classes:
- `FunctionCollector`: CST visitor for function extraction
- `CallCollector`: CST visitor for call relationship mapping

### `engine/hash/` — Semantic Hashing

**Input**: Function CST nodes  
**Output**: Deterministic semantic hashes

Responsibilities:
- Strip docstrings from AST before hashing
- Normalize code structure (optional literal normalization)
- Produce SHA-256 hashes of normalized representation
- Ensure stability across non-behavioral changes

Key Functions:
- `compute_semantic_hash(code: str) -> str`
- `compute_doc_hash(docstring: str) -> str`

### `engine/graph/` — Graph Construction

**Input**: CodeNode objects with hashes  
**Output**: NetworkX DiGraph

Responsibilities:
- Maintain function-level dependency graph
- Store node attributes (hashes, positions, file paths)
- Support incremental updates
- Provide traversal utilities

Key Classes:
- `CodeGraph`: Wrapper around `nx.DiGraph`

### `engine/drift/` — Drift Detection

**Input**: Current graph + stored snapshots  
**Output**: Drift classifications per node

Responsibilities:
- Compare current semantic hashes to stored versions
- Classify each node as FRESH, STALE, or UNDOCUMENTED
- Generate explainable drift reports

Key Classes:
- `DriftDetector`: Main detection logic

### `engine/storage/` — Persistence

**Input**: Graph snapshots  
**Output**: SQLite database

Responsibilities:
- Store node snapshots with timestamps
- Store edge relationships
- Support diff queries between scans
- Maintain scan history

Schema:
```sql
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    file_path TEXT,
    start_line INTEGER,
    end_line INTEGER,
    semantic_hash TEXT,
    doc_hash TEXT,
    last_scanned TIMESTAMP
);

CREATE TABLE edges (
    caller_id TEXT,
    callee_id TEXT,
    PRIMARY KEY (caller_id, callee_id)
);

CREATE TABLE scans (
    scan_id TEXT PRIMARY KEY,
    timestamp TIMESTAMP,
    files_scanned INTEGER
);
```

### `cli/` — User Interface

**Input**: User commands  
**Output**: Rich-formatted terminal output

Responsibilities:
- Parse command-line arguments
- Orchestrate engine components
- Format output with Rich tables and colors
- Provide progress feedback

## Data Flow

### Scan Command (`gdg scan <path>`)

```
1. CLI receives path argument
2. Parser walks directory, extracts functions
3. Hasher computes semantic + doc hashes
4. Graph builds from nodes and edges
5. Storage persists current snapshot
6. CLI reports summary
```

### Status Command (`gdg status`)

```
1. CLI invokes drift detector
2. Detector loads current graph
3. Detector loads previous snapshot from storage
4. Comparator identifies changed hashes
5. Drift classifier assigns states
6. CLI renders Rich table
```

### Explain Command (`gdg explain <id>`)

```
1. CLI parses function ID
2. Detector retrieves node details
3. Comparator shows hash diff
4. CLI renders detailed report
```

## Extension Architecture

The system is designed for extensibility:

```
engine/
├── parser/
│   ├── extractor.py      # Core extraction
│   └── languages/        # Future: language-specific parsers
├── hash/
│   ├── semantic_hash.py  # Core hashing
│   └── strategies/       # Future: alternative hash strategies
├── graph/
│   ├── builder.py        # Core graph
│   └── analyzers/        # Future: graph analysis plugins
└── drift/
    ├── detector.py       # Core detection
    └── reporters/        # Future: output format plugins
```

## Invariants

1. **Graph is authoritative in memory** — SQLite stores snapshots only
2. **Hashes are deterministic** — Same input always produces same hash
3. **No automatic code modification** — Read-only by default
4. **Explicit over implicit** — No "magic" behavior
5. **Fail-safe** — Parsing errors don't crash the system

## Performance Considerations

- LibCST parsing is file-by-file (parallelizable in future)
- NetworkX graphs are in-memory (suitable for codebases < 100K functions)
- SQLite is single-file (no server overhead)
- Incremental updates planned for v2 (only rescan changed files)

## Testing Strategy

Each module has isolated unit tests:

| Module | Test Focus |
|--------|------------|
| Parser | Extraction correctness, edge cases |
| Hash | Stability, normalization |
| Graph | Node/edge operations, traversal |
| Drift | Classification accuracy |
| Storage | CRUD operations, schema |

Integration tests verify end-to-end flows through the CLI.
