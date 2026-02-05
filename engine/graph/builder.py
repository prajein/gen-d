"""
Graph Builder for Gen-D

This module constructs and manages a NetworkX-based dependency graph
where nodes represent functions/methods and edges represent call relationships.

Design Decisions:
    - Uses NetworkX DiGraph for directed call relationships
    - Stores CodeNode objects as node attributes
    - Edges are lightweight (just caller/callee relationship)
    - Graph is authoritative in memory; SQLite stores snapshots only

Academic Context:
    Input: List of CodeNodes and CallEdges from parser
    Transformation: Graph construction with attribute storage
    Output: NetworkX DiGraph with traversal utilities
    Limitation: Static analysis cannot resolve all call targets

Graph Properties:
    - Directed: edges point from caller to callee
    - May have cycles (mutual recursion is valid)
    - May have unresolved edges (callee not in graph)
    - Node IDs are stable qualified names
"""

from pathlib import Path
from typing import Iterator, Optional
import networkx as nx

from engine.models import CodeNode, CallEdge, DriftStatus, ScanResult
from engine.parser import extract_functions_from_file, extract_calls_from_source
from engine.hash import compute_semantic_hash, compute_doc_hash


class CodeGraph:
    """
    A graph representation of a Python codebase.

    Wraps a NetworkX DiGraph to provide a clean interface for:
    - Adding and retrieving function nodes
    - Adding call edges between functions
    - Traversing dependencies
    - Querying graph properties

    The graph uses qualified function names as node identifiers,
    ensuring uniqueness across the codebase.

    Attributes:
        graph: The underlying NetworkX DiGraph
        file_index: Mapping from file paths to their node IDs

    Usage:
        graph = CodeGraph()
        graph.add_node(CodeNode(...))
        graph.add_edge(CallEdge(...))
        for node in graph.get_stale_nodes():
            print(node.id)
    """

    def __init__(self) -> None:
        """Initialize an empty code graph."""
        self._graph: nx.DiGraph = nx.DiGraph()
        self._file_index: dict[str, set[str]] = {}

    @property
    def graph(self) -> nx.DiGraph:
        """Access the underlying NetworkX graph."""
        return self._graph

    @property
    def node_count(self) -> int:
        """Return the number of nodes in the graph."""
        return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        """Return the number of edges in the graph."""
        return self._graph.number_of_edges()

    def add_node(self, node: CodeNode) -> None:
        """
        Add a CodeNode to the graph.

        The node is stored with all its attributes, indexed by its ID.
        If a node with the same ID exists, it will be replaced.

        Args:
            node: The CodeNode to add
        """
        self._graph.add_node(
            node.id,
            code_node=node,
            file_path=node.file_path,
            semantic_hash=node.semantic_hash,
            doc_hash=node.doc_hash,
            drift_status=node.drift_status.value,
        )

        # Update file index
        if node.file_path not in self._file_index:
            self._file_index[node.file_path] = set()
        self._file_index[node.file_path].add(node.id)

    def add_edge(self, edge: CallEdge) -> None:
        """
        Add a call edge to the graph.

        Creates a directed edge from caller to callee. If either node
        doesn't exist in the graph, the edge is still added (NetworkX
        creates placeholder nodes).

        Args:
            edge: The CallEdge to add
        """
        self._graph.add_edge(
            edge.caller_id,
            edge.callee_id,
            call_line=edge.call_line,
        )

    def get_node(self, node_id: str) -> Optional[CodeNode]:
        """
        Retrieve a CodeNode by its ID.

        Args:
            node_id: The unique identifier of the node

        Returns:
            The CodeNode if found, None otherwise
        """
        if node_id not in self._graph:
            return None
        return self._graph.nodes[node_id].get("code_node")

    def get_all_nodes(self) -> Iterator[CodeNode]:
        """
        Iterate over all CodeNodes in the graph.

        Yields:
            Each CodeNode in the graph (in no particular order)
        """
        for node_id in self._graph.nodes:
            node = self._graph.nodes[node_id].get("code_node")
            if node is not None:
                yield node

    def get_nodes_by_file(self, file_path: str) -> Iterator[CodeNode]:
        """
        Get all nodes defined in a specific file.

        Args:
            file_path: Path to the source file

        Yields:
            Each CodeNode defined in the file
        """
        node_ids = self._file_index.get(file_path, set())
        for node_id in node_ids:
            node = self.get_node(node_id)
            if node is not None:
                yield node

    def get_callers(self, node_id: str) -> Iterator[str]:
        """
        Get IDs of all functions that call the given function.

        Args:
            node_id: The callee's identifier

        Yields:
            IDs of calling functions (predecessors)
        """
        if node_id in self._graph:
            yield from self._graph.predecessors(node_id)

    def get_callees(self, node_id: str) -> Iterator[str]:
        """
        Get IDs of all functions called by the given function.

        Args:
            node_id: The caller's identifier

        Yields:
            IDs of called functions (successors)
        """
        if node_id in self._graph:
            yield from self._graph.successors(node_id)

    def get_nodes_by_status(self, status: DriftStatus) -> Iterator[CodeNode]:
        """
        Get all nodes with a specific drift status.

        Args:
            status: The DriftStatus to filter by

        Yields:
            Each CodeNode with the given status
        """
        for node in self.get_all_nodes():
            if node.drift_status == status:
                yield node

    def get_stale_nodes(self) -> list[CodeNode]:
        """
        Get all nodes that have stale documentation.

        Returns:
            List of CodeNodes with STALE drift status
        """
        return list(self.get_nodes_by_status(DriftStatus.STALE))

    def get_undocumented_nodes(self) -> list[CodeNode]:
        """
        Get all nodes without documentation.

        Returns:
            List of CodeNodes with UNDOCUMENTED drift status
        """
        return list(self.get_nodes_by_status(DriftStatus.UNDOCUMENTED))

    def get_fresh_nodes(self) -> list[CodeNode]:
        """
        Get all nodes with fresh documentation.

        Returns:
            List of CodeNodes with FRESH drift status
        """
        return list(self.get_nodes_by_status(DriftStatus.FRESH))

    def update_node_status(self, node_id: str, status: DriftStatus) -> None:
        """
        Update the drift status of a node.

        Args:
            node_id: The node to update
            status: The new drift status
        """
        if node_id in self._graph:
            old_node = self._graph.nodes[node_id].get("code_node")
            if old_node is not None:
                new_node = old_node.with_drift_status(status)
                self._graph.nodes[node_id]["code_node"] = new_node
                self._graph.nodes[node_id]["drift_status"] = status.value

    def get_affected_by_change(self, node_ids: set[str]) -> set[str]:
        """
        Get all nodes affected by changes to the given nodes.

        This includes the changed nodes themselves plus all their callers
        (transitively), as documentation changes may propagate.

        Args:
            node_ids: Set of changed node IDs

        Returns:
            Set of all affected node IDs
        """
        affected = set(node_ids)

        for node_id in node_ids:
            if node_id in self._graph:
                # Add all ancestors (transitive callers)
                ancestors = nx.ancestors(self._graph, node_id)
                affected.update(ancestors)

        return affected

    def clear(self) -> None:
        """Remove all nodes and edges from the graph."""
        self._graph.clear()
        self._file_index.clear()


def build_graph_from_source(
    source: str,
    file_path: str = "<source>",
    module_name: str = "",
) -> CodeGraph:
    """
    Build a CodeGraph from Python source code.

    Parses the source, extracts functions, computes hashes, and
    constructs a graph with nodes and call edges.

    Args:
        source: Python source code as a string
        file_path: Path to attribute to the source
        module_name: Module name for qualified IDs

    Returns:
        A CodeGraph containing all functions and their relationships

    Example:
        >>> source = '''
        ... def main():
        ...     helper()
        ...
        ... def helper():
        ...     pass
        ... '''
        >>> graph = build_graph_from_source(source)
        >>> graph.node_count
        2
    """
    from engine.parser.extractor import (
        extract_functions_from_source,
        extract_calls_from_source,
    )

    graph = CodeGraph()

    # Extract functions
    functions = extract_functions_from_source(source, module_name=module_name)

    # Create nodes
    for func in functions:
        # Compute semantic hash from the complete function source
        semantic_hash = ""
        if func.source_code:
            try:
                semantic_hash = compute_semantic_hash(func.source_code)
            except Exception:
                pass  # Hash computation failed, leave empty

        # Compute doc hash if docstring exists
        doc_hash = None
        if func.docstring:
            doc_hash = compute_doc_hash(func.docstring)

        # Determine initial drift status
        if not func.docstring:
            drift_status = DriftStatus.UNDOCUMENTED
        else:
            drift_status = DriftStatus.FRESH  # Will be updated by drift detector

        node = CodeNode(
            id=f"{file_path}:{func.qualified_name}",
            name=func.name,
            file_path=file_path,
            start_line=func.start_line,
            end_line=func.end_line,
            semantic_hash=semantic_hash,
            doc_hash=doc_hash,
            drift_status=drift_status,
            is_method=func.is_method,
            class_name=func.class_name,
            docstring=func.docstring,
        )
        graph.add_node(node)

    # Extract and add call edges
    calls = extract_calls_from_source(source, module_name=module_name)
    for call in calls:
        caller_id = f"{file_path}:{call.caller_qualified_name}"
        # For now, use simple callee name; resolution would require more context
        callee_id = f"{file_path}:{call.callee_name}"

        edge = CallEdge(
            caller_id=caller_id,
            callee_id=callee_id,
            call_line=call.call_line,
        )
        graph.add_edge(edge)

    return graph


def build_graph_from_directory(
    directory: Path | str,
    exclude_patterns: Optional[list[str]] = None,
) -> ScanResult:
    """
    Build a CodeGraph from all Python files in a directory.

    Recursively scans the directory for .py files, extracts functions
    from each, and builds a unified graph.

    Args:
        directory: Path to the directory to scan
        exclude_patterns: Glob patterns to exclude (e.g., ["**/test_*.py"])

    Returns:
        ScanResult containing the graph, nodes, edges, and any errors

    Example:
        >>> result = build_graph_from_directory("./my_project")
        >>> print(f"Found {result.node_count} functions in {result.files_scanned} files")
    """
    import time
    from engine.parser.extractor import (
        extract_functions_from_source,
        extract_calls_from_source,
    )

    start_time = time.time()
    directory = Path(directory)

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    # Default exclusions
    if exclude_patterns is None:
        exclude_patterns = [
            "**/__pycache__/**",
            "**/.*",
            "**/*.pyc",
        ]

    result = ScanResult()
    graph = CodeGraph()

    # Find all Python files
    py_files = list(directory.rglob("*.py"))

    for file_path in py_files:
        # Check exclusion patterns
        relative_path = file_path.relative_to(directory)
        should_exclude = False
        for pattern in exclude_patterns:
            if relative_path.match(pattern):
                should_exclude = True
                break

        if should_exclude:
            continue

        try:
            source = file_path.read_text(encoding="utf-8")
            module_name = _path_to_module_name(file_path, directory)

            # Extract functions
            functions = extract_functions_from_source(source, module_name=module_name)

            for func in functions:
                # Compute hashes using the complete function source from parser
                semantic_hash = ""
                if func.source_code:
                    try:
                        semantic_hash = compute_semantic_hash(func.source_code)
                    except Exception:
                        pass  # Hash computation failed

                doc_hash = None
                if func.docstring:
                    doc_hash = compute_doc_hash(func.docstring)

                drift_status = DriftStatus.UNDOCUMENTED if not func.docstring else DriftStatus.FRESH

                node = CodeNode(
                    id=f"{str(file_path)}:{func.qualified_name}",
                    name=func.name,
                    file_path=str(file_path),
                    start_line=func.start_line,
                    end_line=func.end_line,
                    semantic_hash=semantic_hash,
                    doc_hash=doc_hash,
                    drift_status=drift_status,
                    is_method=func.is_method,
                    class_name=func.class_name,
                    docstring=func.docstring,
                )
                graph.add_node(node)
                result.nodes.append(node)

            # Extract calls
            calls = extract_calls_from_source(source, module_name=module_name)
            for call in calls:
                caller_id = f"{str(file_path)}:{call.caller_qualified_name}"
                callee_id = f"{str(file_path)}:{call.callee_name}"

                edge = CallEdge(
                    caller_id=caller_id,
                    callee_id=callee_id,
                    call_line=call.call_line,
                )
                graph.add_edge(edge)
                result.edges.append(edge)

            result.files_scanned += 1

        except Exception as e:
            result.errors.append((str(file_path), str(e)))

    result.scan_time_seconds = time.time() - start_time

    return result


def _extract_function_source(source: str, start_line: int, end_line: int) -> str:
    """
    Extract the source code of a function from full file source.

    Args:
        source: Full source code of the file
        start_line: 1-indexed starting line
        end_line: 1-indexed ending line

    Returns:
        The function's source code
    """
    lines = source.splitlines()
    if start_line < 1 or end_line > len(lines):
        return ""
    return "\n".join(lines[start_line - 1 : end_line])


def _path_to_module_name(file_path: Path, base_dir: Path) -> str:
    """
    Convert a file path to a Python module name.

    Args:
        file_path: Path to the Python file
        base_dir: Base directory of the project

    Returns:
        Dotted module name (e.g., "engine.parser.extractor")
    """
    try:
        relative = file_path.relative_to(base_dir)
        parts = list(relative.parts)
        # Remove .py extension from last part
        if parts and parts[-1].endswith(".py"):
            parts[-1] = parts[-1][:-3]
        return ".".join(parts)
    except ValueError:
        return file_path.stem
