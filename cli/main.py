"""
Gen-D CLI

Command-line interface for the living documentation engine.
Provides commands for scanning codebases, checking documentation status,
and explaining drift for specific functions.

Commands:
    gdg scan <path>     Scan a Python codebase and build the dependency graph
    gdg status          Display documentation drift summary
    gdg explain <id>    Show detailed drift information for a specific function

Usage:
    $ gdg scan ./my-project
    $ gdg status
    $ gdg explain my_module:MyClass.my_method
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from engine.graph import build_graph_from_directory
from engine.drift import DriftDetector, analyze_codebase_drift
from engine.storage import Database
from engine.models import DriftStatus

# Initialize Typer app and Rich console
app = typer.Typer(
    name="gdg",
    help="Gen-D: A living documentation engine for Python codebases",
    add_completion=False,
)
console = Console()


# Default paths
DEFAULT_DB_PATH = ".gen-d/gen-d.db"


@app.command()
def scan(
    path: Path = typer.Argument(
        ...,
        help="Path to the Python project to scan",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        "-d",
        help="Path to the database file (default: .gen-d/gen-d.db in project)",
    ),
) -> None:
    """
    Scan a Python codebase and build the dependency graph.

    This command:
    1. Recursively finds all .py files in the directory
    2. Extracts function and method definitions
    3. Computes semantic hashes for drift detection
    4. Stores snapshots in the database
    """
    # Determine database path
    if db_path is None:
        db_path = path / DEFAULT_DB_PATH

    console.print(f"\n[bold blue]📂 Scanning:[/bold blue] {path}\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Scanning phase
        task = progress.add_task("Parsing Python files...", total=None)

        try:
            result = build_graph_from_directory(path)
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(1)

        progress.update(task, description="Saving to database...")

        # Save to database
        db = Database(db_path)
        scan_id = db.record_scan(
            directory=str(path),
            files_scanned=result.files_scanned,
            nodes_found=result.node_count,
            errors=result.error_count,
        )
        db.save_nodes(result.nodes, scan_id=scan_id)
        db.save_edges(result.edges)

        progress.update(task, description="Done!")

    # Print summary
    console.print()
    _print_scan_summary(result, db_path)

    # Show errors if any
    if result.errors:
        console.print(f"\n[yellow]⚠️  {result.error_count} file(s) had parse errors:[/yellow]")
        for file_path, error in result.errors[:5]:
            console.print(f"   • {file_path}: {error}")
        if result.error_count > 5:
            console.print(f"   ... and {result.error_count - 5} more")


@app.command()
def status(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to the project (default: current directory)",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        "-d",
        help="Path to the database file",
    ),
    show_all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Show all stale functions, not just top 5",
    ),
) -> None:
    """
    Display documentation drift summary.

    Shows:
    - Count of fresh, stale, and undocumented functions
    - Top stale functions that need attention
    - Overall documentation health
    """
    # Resolve paths
    if path is None:
        path = Path.cwd()

    if db_path is None:
        db_path = path / DEFAULT_DB_PATH

    # Check if database exists
    if not db_path.exists():
        console.print(
            f"[yellow]No scan data found.[/yellow] Run [bold]gdg scan {path}[/bold] first."
        )
        raise typer.Exit(1)

    # Load data
    db = Database(db_path)
    snapshots = db.load_snapshots()

    if not snapshots:
        console.print("[yellow]No functions found in database.[/yellow]")
        raise typer.Exit(0)

    # For status, we need to re-scan to compare current vs stored
    # In a production system, we might cache this or use file watching
    console.print(f"\n[bold blue]📊 Documentation Status:[/bold blue] {path}\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing drift...", total=None)

        try:
            result = build_graph_from_directory(path)
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(1)

        # Detect drift
        detector = DriftDetector(snapshots)
        report = detector.generate_report(result.nodes)

        progress.update(task, description="Done!")

    # Print status table
    _print_status_table(report)

    # Print stale functions
    if report.stale_nodes:
        limit = None if show_all else 5
        _print_stale_list(report.stale_nodes, detector, result.nodes, limit)

    # Print undocumented summary
    if report.undocumented_nodes:
        console.print(
            f"\n[dim]💡 {report.undocumented_count} function(s) are undocumented. "
            f"Use [bold]gdg explain <id>[/bold] for details.[/dim]"
        )


@app.command()
def explain(
    function_id: str = typer.Argument(
        ...,
        help="Function ID to explain (e.g., module:function or file.py:Class.method)",
    ),
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to the project (default: current directory)",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        "-d",
        help="Path to the database file",
    ),
) -> None:
    """
    Show detailed drift information for a specific function.

    Provides:
    - Current drift status with explanation
    - Hash comparison (current vs stored)
    - Actionable suggestions
    """
    # Resolve paths
    if path is None:
        path = Path.cwd()

    if db_path is None:
        db_path = path / DEFAULT_DB_PATH

    # Check if database exists
    if not db_path.exists():
        console.print(
            f"[yellow]No scan data found.[/yellow] Run [bold]gdg scan {path}[/bold] first."
        )
        raise typer.Exit(1)

    # Load data
    db = Database(db_path)
    snapshots = db.load_snapshots()

    # Re-scan to get current state
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Loading...", total=None)

        try:
            result = build_graph_from_directory(path)
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(1)

        progress.update(task, description="Done!")

    # Find the node
    node = None
    for n in result.nodes:
        if n.id == function_id or n.id.endswith(f":{function_id}"):
            node = n
            break

    if node is None:
        # Try partial match
        matches = [n for n in result.nodes if function_id in n.id]
        if matches:
            console.print(f"[yellow]Function '{function_id}' not found. Did you mean:[/yellow]")
            for m in matches[:5]:
                console.print(f"   • {m.id}")
        else:
            console.print(f"[red]Function '{function_id}' not found.[/red]")
        raise typer.Exit(1)

    # Generate explanation
    detector = DriftDetector(snapshots)
    explanation = detector.explain(node)

    # Print explanation
    _print_explanation(explanation, node)


@app.command()
def history(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to the project (default: current directory)",
    ),
    db_path: Optional[Path] = typer.Option(
        None,
        "--db",
        "-d",
        help="Path to the database file",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-n",
        help="Number of scans to show",
    ),
) -> None:
    """
    Show scan history.
    """
    if path is None:
        path = Path.cwd()

    if db_path is None:
        db_path = path / DEFAULT_DB_PATH

    if not db_path.exists():
        console.print("[yellow]No scan history found.[/yellow]")
        raise typer.Exit(0)

    db = Database(db_path)
    scans = db.get_scan_history(limit)

    if not scans:
        console.print("[yellow]No scans recorded.[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Scan History", box=box.ROUNDED)
    table.add_column("Timestamp", style="cyan")
    table.add_column("Files", justify="right")
    table.add_column("Functions", justify="right")
    table.add_column("Errors", justify="right")

    for scan in scans:
        table.add_row(
            scan.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            str(scan.files_scanned),
            str(scan.nodes_found),
            str(scan.errors) if scan.errors else "-",
        )

    console.print(table)


# Helper functions for output formatting

def _print_scan_summary(result, db_path: Path) -> None:
    """Print a summary panel after scanning."""
    table = Table(box=box.SIMPLE, show_header=False)
    table.add_column("Label", style="dim")
    table.add_column("Value", style="bold")

    table.add_row("Files scanned", str(result.files_scanned))
    table.add_row("Functions found", str(result.node_count))
    table.add_row("Call edges", str(result.edge_count))
    table.add_row("Parse errors", str(result.error_count) if result.errors else "0")
    table.add_row("Scan time", f"{result.scan_time_seconds:.2f}s")
    table.add_row("Database", str(db_path))

    panel = Panel(table, title="[bold green]✓ Scan Complete[/bold green]", border_style="green")
    console.print(panel)


def _print_status_table(report) -> None:
    """Print the drift status summary table."""
    table = Table(box=box.ROUNDED)
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")

    total = report.total_nodes
    if total == 0:
        console.print("[yellow]No functions to analyze.[/yellow]")
        return

    table.add_row(
        "[green]✓ Fresh[/green]",
        str(report.fresh_count),
        f"{(report.fresh_count / total) * 100:.1f}%",
    )
    table.add_row(
        "[yellow]⚠ Stale[/yellow]",
        str(report.stale_count),
        f"{(report.stale_count / total) * 100:.1f}%",
    )
    table.add_row(
        "[dim]○ Undocumented[/dim]",
        str(report.undocumented_count),
        f"{(report.undocumented_count / total) * 100:.1f}%",
    )
    table.add_row("", "", "")
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]", "100%")

    console.print(table)


def _print_stale_list(stale_ids, detector, nodes, limit=5) -> None:
    """Print the list of stale functions."""
    console.print(f"\n[bold yellow]⚠️  Stale Documentation ({len(stale_ids)} total):[/bold yellow]")

    display_ids = stale_ids[:limit] if limit else stale_ids

    for node_id in display_ids:
        # Find the node for display
        short_id = node_id.split(":")[-1] if ":" in node_id else node_id
        file_info = node_id.split(":")[0] if ":" in node_id else ""
        file_short = Path(file_info).name if file_info else ""

        console.print(f"   • [cyan]{short_id}[/cyan] [dim]({file_short})[/dim]")

    if limit and len(stale_ids) > limit:
        console.print(f"   [dim]... and {len(stale_ids) - limit} more[/dim]")

    console.print(f"\n[dim]Run [bold]gdg explain <function_id>[/bold] for details.[/dim]")


def _print_explanation(explanation, node) -> None:
    """Print detailed explanation for a function."""
    # Status color
    status_colors = {
        DriftStatus.FRESH: "green",
        DriftStatus.STALE: "yellow",
        DriftStatus.UNDOCUMENTED: "dim",
    }
    status_icons = {
        DriftStatus.FRESH: "✓",
        DriftStatus.STALE: "⚠",
        DriftStatus.UNDOCUMENTED: "○",
    }

    color = status_colors[explanation.current_status]
    icon = status_icons[explanation.current_status]

    console.print(f"\n[bold]Function:[/bold] {node.name}")
    console.print(f"[bold]File:[/bold] {node.file_path}")
    console.print(f"[bold]Lines:[/bold] {node.start_line}-{node.end_line}")
    console.print(
        f"[bold]Status:[/bold] [{color}]{icon} {explanation.current_status.value.upper()}[/{color}]"
    )

    console.print(f"\n[bold]Reason:[/bold]")
    console.print(f"   {explanation.reason}")

    # Hash details
    console.print(f"\n[bold]Hashes:[/bold]")
    console.print(f"   Current semantic: [cyan]{explanation.current_semantic_hash[:16]}...[/cyan]")
    if explanation.stored_semantic_hash:
        console.print(
            f"   Stored semantic:  [dim]{explanation.stored_semantic_hash[:16]}...[/dim]"
        )
    if explanation.current_doc_hash:
        console.print(f"   Current doc:      [cyan]{explanation.current_doc_hash[:16]}...[/cyan]")
    if explanation.stored_doc_hash:
        console.print(f"   Stored doc:       [dim]{explanation.stored_doc_hash[:16]}...[/dim]")

    # Suggestions
    console.print(f"\n[bold]Suggestions:[/bold]")
    for suggestion in explanation.suggestions:
        console.print(f"   • {suggestion}")

    # Show docstring if exists
    if node.docstring:
        console.print(f"\n[bold]Current Docstring:[/bold]")
        docstring_preview = node.docstring[:200]
        if len(node.docstring) > 200:
            docstring_preview += "..."
        console.print(Panel(docstring_preview, border_style="dim"))


# Version command
@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
    ),
) -> None:
    """
    Gen-D: A living documentation engine for Python codebases.
    """
    if version:
        console.print("[bold]Gen-D[/bold] version 0.1.0")
        raise typer.Exit()


if __name__ == "__main__":
    app()
