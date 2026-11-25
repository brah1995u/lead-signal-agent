from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .evaluate import evaluate, load_dataset
from .export import to_csv, to_google_sheets
from .icp import load_icp
from .llm import select_llm
from .models import Lead
from .pipeline import run as run_pipeline
from .sources import FirecrawlSource, HackerNewsSource, Source
from .store import Store

app = typer.Typer(
    add_completion=False, help="Find public conversations with buying intent and score them against your ICP."
)
console = Console()

DbOption = Annotated[Path, typer.Option(help="SQLite file with signals and scores")]


def _sources(names: list[str]) -> list[Source]:
    sources: list[Source] = []
    for name in names:
        if name == "hn":
            sources.append(HackerNewsSource())
        elif name == "web":
            key = os.getenv("FIRECRAWL_API_KEY")
            if not key:
                raise typer.BadParameter("--source web needs FIRECRAWL_API_KEY")
            sites = [
                s for s in os.getenv("WEB_SITES", "reddit.com,quora.com,indiehackers.com").split(",") if s
            ]
            sources.append(FirecrawlSource(key, sites=sites))
        else:
            raise typer.BadParameter(f"Unknown source {name} (use hn or web)")
    return sources


def _table(leads: list[Lead], title: str) -> Table:
    table = Table(title=title, show_lines=True)
    table.add_column("Score", justify="right", style="bold")
    table.add_column("Intent")
    table.add_column("Need", max_width=48)
    table.add_column("Opener", max_width=44, style="dim")
    table.add_column("Link", max_width=40, overflow="fold")
    for lead in leads:
        q = lead.qualification
        style = "green" if q.fit_score >= 80 else "yellow"
        table.add_row(
            f"[{style}]{q.fit_score}[/]",
            q.intent.value.replace("_", " "),
            q.summary,
            q.suggested_opener,
            lead.signal.url,
        )
    return table


@app.command()
def run(
    icp: Annotated[Path, typer.Option(help="ICP file (YAML)")] = Path("examples/icp.example.yaml"),
    source: Annotated[list[str], typer.Option(help="hn (default, no key) and/or web (Firecrawl)")] = ["hn"],  # noqa: B006
    query: Annotated[list[str] | None, typer.Option(help="Skip planning and use these queries")] = None,
    per_query: int = 25,
    db: DbOption = Path(".data/leads.db"),
    csv: Annotated[Path | None, typer.Option(help="Also write leads to this CSV")] = None,
):
    """Plan queries, search, dedupe, score new signals and show the best leads."""
    profile = load_icp(icp)
    llm = select_llm()
    console.print(f"[dim]Model: {llm.model}[/]")
    report = run_pipeline(
        profile,
        _sources(source),
        llm,
        Store(db),
        per_query=per_query,
        queries=query,
        progress=lambda m: console.print(f"[dim]· {m}[/]"),
    )
    for error in report.errors:
        console.print(f"[yellow]! {error}[/]")
    console.print(
        f"Found {report.found} · new {report.new} · scored {report.judged} · leads ≥ {profile.min_score}: {len(report.leads)}"
    )
    console.print(_table(report.leads[:20], "Top leads"))
    if csv:
        console.print(f"CSV: {to_csv(report.leads, csv)}")


@app.command()
def leads(min_score: int = 60, limit: int = 20, db: DbOption = Path(".data/leads.db")):
    """Show stored leads, best first."""
    console.print(_table(Store(db).leads(min_score=min_score, limit=limit), f"Leads ≥ {min_score}"))


@app.command()
def export(
    csv: Annotated[Path | None, typer.Option(help="CSV file to write")] = None,
    sheet: Annotated[
        str | None, typer.Option(help="Google Sheets spreadsheet name (shared with the service account)")
    ] = None,
    credentials: Annotated[Path | None, typer.Option(help="Service-account JSON for Google Sheets")] = None,
    min_score: int = 60,
    db: DbOption = Path(".data/leads.db"),
):
    """Export stored leads to CSV and/or Google Sheets."""
    items = Store(db).leads(min_score=min_score, limit=10_000)
    if csv:
        console.print(f"CSV: {to_csv(items, csv)}")
    if sheet:
        if not credentials:
            raise typer.BadParameter("--sheet needs --credentials")
        console.print(f"Sheet: {to_google_sheets(items, sheet, str(credentials))}")


@app.command(name="eval")
def eval_command(
    dataset: Path = Path("evals/labeled_signals.jsonl"),
    icp: Path = Path("evals/icp.yaml"),
):
    """Measure qualification precision / recall on the labeled dataset."""
    llm = select_llm()
    result = evaluate(load_dataset(dataset), load_icp(icp), llm)
    console.print(f"Model {llm.model} · {result.judged}/{result.total} judged")
    console.print(
        f"precision {result.precision:.2f} · recall {result.recall:.2f} · F1 {result.f1:.2f} · "
        f"intent accuracy {result.intent_correct / result.total:.2f}"
    )
    for m in result.mistakes:
        console.print(f"[yellow]  {m}[/]")


if __name__ == "__main__":
    app()
