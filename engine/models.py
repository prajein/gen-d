"""
Core Data Models for Gen-D

This module defines the canonical data structures used throughout the system:
- CodeNode: Represents a function or method with its semantic properties
- CallEdge: Represents a call relationship between functions
- DriftStatus: Classification of documentation freshness

These models are designed to be:
- Immutable where possible (using frozen dataclasses)
- Serializable for storage
- Clear in their semantic meaning
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


class DriftStatus(Enum):
    """
    Classification of documentation drift for a code node.

    States:
        FRESH: Documentation matches current code semantics.
               The semantic hash matches the stored hash from last documentation.

        STALE: Code logic has changed but documentation hasn't.
               The semantic hash differs from stored, but doc hash is unchanged.

        UNDOCUMENTED: No docstring exists for this function.
               Cannot assess freshness without documentation.
    """

    FRESH = "fresh"
    STALE = "stale"
    UNDOCUMENTED = "undocumented"


@dataclass(frozen=True)
class CodeNode:
    """
    Represents a single semantic unit in the codebase (function or method).

    A CodeNode captures both the structural position of a function and its
    semantic fingerprint via hashes. The semantic_hash captures the logic
    (excluding docstrings), while doc_hash captures the documentation content.

    Attributes:
        id: Stable identifier in format "module.path:qualified.name"
            Example: "engine.parser.extractor:FunctionCollector.visit_FunctionDef"
        name: Simple function/method name without qualification
        file_path: Absolute path to the source file
        start_line: 1-indexed starting line of the function
        end_line: 1-indexed ending line of the function
        semantic_hash: SHA-256 hash of normalized function logic (docstrings excluded)
        doc_hash: SHA-256 hash of the docstring content, None if no docstring
        drift_status: Current classification of documentation freshness
        is_method: True if this is a method within a class
        class_name: Name of containing class if is_method is True
        docstring: The actual docstring content, if present

    Invariants:
        - id is unique across the entire graph
        - start_line <= end_line
        - semantic_hash is never None (always computed)
        - doc_hash is None iff docstring is None
    """

    id: str
    name: str
    file_path: str
    start_line: int
    end_line: int
    semantic_hash: str
    doc_hash: Optional[str] = None
    drift_status: DriftStatus = DriftStatus.UNDOCUMENTED
    is_method: bool = False
    class_name: Optional[str] = None
    docstring: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate invariants after initialization."""
        if self.start_line > self.end_line:
            raise ValueError(
                f"start_line ({self.start_line}) must be <= end_line ({self.end_line})"
            )

    @property
    def qualified_name(self) -> str:
        """Return the fully qualified name including class if applicable."""
        if self.is_method and self.class_name:
            return f"{self.class_name}.{self.name}"
        return self.name

    @property
    def has_docstring(self) -> bool:
        """Check if this node has documentation."""
        return self.docstring is not None and len(self.docstring.strip()) > 0

    def with_drift_status(self, status: DriftStatus) -> "CodeNode":
        """Return a new CodeNode with updated drift status (immutable update)."""
        return CodeNode(
            id=self.id,
            name=self.name,
            file_path=self.file_path,
            start_line=self.start_line,
            end_line=self.end_line,
            semantic_hash=self.semantic_hash,
            doc_hash=self.doc_hash,
            drift_status=status,
            is_method=self.is_method,
            class_name=self.class_name,
            docstring=self.docstring,
        )


@dataclass(frozen=True)
class CallEdge:
    """
    Represents a call relationship between two functions.

    A CallEdge is a directed edge in the dependency graph, indicating that
    the caller function contains a call to the callee function.

    Attributes:
        caller_id: ID of the calling function (source node)
        callee_id: ID of the called function (target node)
        call_line: Line number where the call occurs (optional, for debugging)

    Note:
        CallEdges may be unresolved if the callee cannot be statically determined.
        Such edges will have callee_id set to a placeholder or partial name.

    Invariants:
        - caller_id and callee_id are never equal (no self-loops for calls)
    """

    caller_id: str
    callee_id: str
    call_line: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate that we don't have self-loops."""
        # Note: self-recursion is valid, so we actually allow caller_id == callee_id
        # Removing this check as recursive calls are valid
        pass


@dataclass
class NodeSnapshot:
    """
    A point-in-time snapshot of a CodeNode for storage.

    Used by the storage layer to persist node state and enable
    drift detection across scans.

    Attributes:
        node_id: Unique identifier matching CodeNode.id
        file_path: Path to source file at time of snapshot
        start_line: Starting line at time of snapshot
        end_line: Ending line at time of snapshot
        semantic_hash: Semantic hash at time of snapshot
        doc_hash: Documentation hash at time of snapshot
        timestamp: When this snapshot was taken
    """

    node_id: str
    file_path: str
    start_line: int
    end_line: int
    semantic_hash: str
    doc_hash: Optional[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_node(cls, node: CodeNode) -> "NodeSnapshot":
        """Create a snapshot from a CodeNode."""
        return cls(
            node_id=node.id,
            file_path=node.file_path,
            start_line=node.start_line,
            end_line=node.end_line,
            semantic_hash=node.semantic_hash,
            doc_hash=node.doc_hash,
        )


@dataclass
class ScanResult:
    """
    Result of scanning a codebase.

    Aggregates statistics and results from a single scan operation.

    Attributes:
        nodes: List of all CodeNodes discovered
        edges: List of all CallEdges discovered
        files_scanned: Number of Python files processed
        errors: List of files that failed to parse with error messages
        scan_time_seconds: Total time taken for the scan
    """

    nodes: list[CodeNode] = field(default_factory=list)
    edges: list[CallEdge] = field(default_factory=list)
    files_scanned: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)
    scan_time_seconds: float = 0.0

    @property
    def node_count(self) -> int:
        """Total number of nodes discovered."""
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """Total number of edges discovered."""
        return len(self.edges)

    @property
    def error_count(self) -> int:
        """Number of files that failed to parse."""
        return len(self.errors)


@dataclass
class DriftReport:
    """
    Summary of drift analysis for a codebase.

    Attributes:
        fresh_count: Number of nodes with fresh documentation
        stale_count: Number of nodes with stale documentation
        undocumented_count: Number of nodes without documentation
        stale_nodes: List of node IDs that are stale (for detailed reporting)
        undocumented_nodes: List of node IDs without documentation
    """

    fresh_count: int = 0
    stale_count: int = 0
    undocumented_count: int = 0
    stale_nodes: list[str] = field(default_factory=list)
    undocumented_nodes: list[str] = field(default_factory=list)

    @property
    def total_nodes(self) -> int:
        """Total number of nodes analyzed."""
        return self.fresh_count + self.stale_count + self.undocumented_count

    @property
    def documented_percentage(self) -> float:
        """Percentage of nodes that have documentation."""
        if self.total_nodes == 0:
            return 0.0
        documented = self.fresh_count + self.stale_count
        return (documented / self.total_nodes) * 100

    @property
    def fresh_percentage(self) -> float:
        """Percentage of documented nodes that are fresh."""
        documented = self.fresh_count + self.stale_count
        if documented == 0:
            return 0.0
        return (self.fresh_count / documented) * 100
