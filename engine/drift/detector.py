"""
Drift Detection for Gen-D

This module implements the core drift detection logic, comparing current
code semantics against stored snapshots to identify documentation that
has become stale.

Drift States:
    FRESH: Documentation matches current code semantics
           - semantic_hash matches stored hash
           - OR docstring has been updated since code change

    STALE: Code logic has changed but documentation hasn't
           - semantic_hash differs from stored hash
           - AND doc_hash remains unchanged

    UNDOCUMENTED: No docstring exists for this function
           - Cannot assess freshness without documentation

Academic Context:
    Input: Current CodeNodes + Stored NodeSnapshots
    Transformation: Hash comparison with state classification
    Output: Updated drift status for each node
    Limitation: Depends on hash quality for semantic equivalence

Design Decisions:
    - Deterministic: Same inputs always produce same classifications
    - Explainable: Each classification can be justified with hash diffs
    - Conservative: When in doubt, mark as STALE (false positives preferred)
"""

from dataclasses import dataclass
from typing import Optional
from engine.models import CodeNode, DriftStatus, DriftReport, NodeSnapshot


@dataclass
class DriftExplanation:
    """
    Detailed explanation of why a node has its current drift status.

    Used by the `explain` CLI command to provide actionable information.

    Attributes:
        node_id: The function's unique identifier
        current_status: The detected drift status
        reason: Human-readable explanation
        current_semantic_hash: Current hash of code logic
        stored_semantic_hash: Stored hash from last documentation
        current_doc_hash: Current hash of docstring
        stored_doc_hash: Stored hash of docstring from last scan
        suggestions: Action items for the developer
    """

    node_id: str
    current_status: DriftStatus
    reason: str
    current_semantic_hash: str
    stored_semantic_hash: Optional[str]
    current_doc_hash: Optional[str]
    stored_doc_hash: Optional[str]
    suggestions: list[str]


class DriftDetector:
    """
    Detects documentation drift by comparing code semantics to stored state.

    The detector maintains a reference to stored snapshots and compares
    them against current node states to classify drift.

    Usage:
        detector = DriftDetector(stored_snapshots)
        status = detector.detect(current_node)
        explanation = detector.explain(current_node)
    """

    def __init__(
        self,
        stored_snapshots: Optional[dict[str, NodeSnapshot]] = None,
    ) -> None:
        """
        Initialize the detector with stored snapshots.

        Args:
            stored_snapshots: Dictionary mapping node IDs to their last snapshots.
                              If None, all documented nodes are considered FRESH.
        """
        self._snapshots = stored_snapshots or {}

    def detect(self, node: CodeNode) -> DriftStatus:
        """
        Detect the drift status of a single node.

        Classification Rules:
            1. If no docstring → UNDOCUMENTED
            2. If no stored snapshot → FRESH (new node)
            3. If semantic_hash matches → FRESH (unchanged)
            4. If doc_hash changed → FRESH (docs updated)
            5. Otherwise → STALE (code changed, docs didn't)

        Args:
            node: The current CodeNode to analyze

        Returns:
            The detected DriftStatus
        """
        return detect_node_drift(node, self._snapshots.get(node.id))

    def detect_all(self, nodes: list[CodeNode]) -> list[CodeNode]:
        """
        Detect drift status for all nodes and return updated nodes.

        Args:
            nodes: List of current CodeNodes

        Returns:
            List of CodeNodes with updated drift_status
        """
        updated_nodes = []
        for node in nodes:
            status = self.detect(node)
            updated_node = node.with_drift_status(status)
            updated_nodes.append(updated_node)
        return updated_nodes

    def explain(self, node: CodeNode) -> DriftExplanation:
        """
        Generate a detailed explanation of a node's drift status.

        Args:
            node: The CodeNode to explain

        Returns:
            DriftExplanation with full details and suggestions
        """
        snapshot = self._snapshots.get(node.id)
        status = self.detect(node)

        stored_semantic = snapshot.semantic_hash if snapshot else None
        stored_doc = snapshot.doc_hash if snapshot else None

        # Build explanation based on status
        if status == DriftStatus.UNDOCUMENTED:
            reason = "This function has no docstring."
            suggestions = [
                "Add a docstring describing the function's purpose",
                "Document parameters and return values",
                "Include usage examples if complex",
            ]
        elif status == DriftStatus.FRESH:
            if snapshot is None:
                reason = "This is a new function with documentation."
            elif node.semantic_hash == stored_semantic:
                reason = "Code logic is unchanged since last documentation."
            else:
                reason = "Documentation was updated after code changes."
            suggestions = ["No action needed."]
        else:  # STALE
            reason = (
                f"Code logic changed (hash differs) but docstring unchanged.\n"
                f"  - Old code hash: {stored_semantic[:16]}...\n"
                f"  - New code hash: {node.semantic_hash[:16]}..."
            )
            suggestions = [
                "Review the code changes since last documentation",
                "Update the docstring to reflect current behavior",
                "Run 'gdg scan' again after updating",
            ]

        return DriftExplanation(
            node_id=node.id,
            current_status=status,
            reason=reason,
            current_semantic_hash=node.semantic_hash,
            stored_semantic_hash=stored_semantic,
            current_doc_hash=node.doc_hash,
            stored_doc_hash=stored_doc,
            suggestions=suggestions,
        )

    def generate_report(self, nodes: list[CodeNode]) -> DriftReport:
        """
        Generate a summary report of drift across all nodes.

        Args:
            nodes: List of CodeNodes to analyze

        Returns:
            DriftReport with counts and lists of affected nodes
        """
        return analyze_codebase_drift(nodes, self._snapshots)

    def add_snapshot(self, snapshot: NodeSnapshot) -> None:
        """
        Add or update a stored snapshot.

        Args:
            snapshot: The NodeSnapshot to store
        """
        self._snapshots[snapshot.node_id] = snapshot

    def add_snapshots(self, snapshots: list[NodeSnapshot]) -> None:
        """
        Add multiple snapshots at once.

        Args:
            snapshots: List of NodeSnapshots to store
        """
        for snapshot in snapshots:
            self.add_snapshot(snapshot)


def detect_node_drift(
    node: CodeNode,
    stored: Optional[NodeSnapshot],
) -> DriftStatus:
    """
    Detect drift status for a single node against its stored snapshot.

    This is a pure function implementing the drift classification rules.

    Args:
        node: The current state of the code node
        stored: The stored snapshot from last documentation, or None

    Returns:
        The detected DriftStatus

    Rules (in order):
        1. No docstring → UNDOCUMENTED
        2. No stored snapshot → FRESH (new node)
        3. Semantic hash unchanged → FRESH
        4. Doc hash changed → FRESH (docs updated)
        5. Otherwise → STALE
    """
    # Rule 1: No docstring
    if not node.has_docstring:
        return DriftStatus.UNDOCUMENTED

    # Rule 2: No stored snapshot (new node)
    if stored is None:
        return DriftStatus.FRESH

    # Rule 3: Semantic hash unchanged
    if node.semantic_hash == stored.semantic_hash:
        return DriftStatus.FRESH

    # Rule 4: Doc hash changed (documentation was updated)
    if node.doc_hash != stored.doc_hash:
        return DriftStatus.FRESH

    # Rule 5: Code changed but docs didn't
    return DriftStatus.STALE


def analyze_codebase_drift(
    nodes: list[CodeNode],
    stored_snapshots: Optional[dict[str, NodeSnapshot]] = None,
) -> DriftReport:
    """
    Analyze drift across an entire codebase.

    Args:
        nodes: List of all CodeNodes in the codebase
        stored_snapshots: Dictionary of stored snapshots keyed by node ID

    Returns:
        DriftReport with comprehensive statistics

    Example:
        >>> nodes = [node1, node2, node3]
        >>> snapshots = {"node1": snapshot1, "node2": snapshot2}
        >>> report = analyze_codebase_drift(nodes, snapshots)
        >>> print(f"Stale: {report.stale_count}, Fresh: {report.fresh_count}")
    """
    stored_snapshots = stored_snapshots or {}

    fresh_count = 0
    stale_count = 0
    undocumented_count = 0
    stale_nodes: list[str] = []
    undocumented_nodes: list[str] = []

    for node in nodes:
        status = detect_node_drift(node, stored_snapshots.get(node.id))

        if status == DriftStatus.FRESH:
            fresh_count += 1
        elif status == DriftStatus.STALE:
            stale_count += 1
            stale_nodes.append(node.id)
        else:
            undocumented_count += 1
            undocumented_nodes.append(node.id)

    return DriftReport(
        fresh_count=fresh_count,
        stale_count=stale_count,
        undocumented_count=undocumented_count,
        stale_nodes=stale_nodes,
        undocumented_nodes=undocumented_nodes,
    )
