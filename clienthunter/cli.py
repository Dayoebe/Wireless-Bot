from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .auditor import WebsiteAuditor
from .database import (
    VALID_LEAD_STATUSES,
    delete_lead,
    get_lead,
    init_db,
    list_leads,
    save_lead,
    update_lead_status,
)
from .discovery import LeadDiscovery
from .exporter import export_leads
from .outreach import build_outreach

app = typer.Typer(help="Wireless Bot: audit websites, score leads, and generate outreach.")
console = Console()


@app.command()
def initdb():
    """Create the local SQLite database."""
    init_db()
    console.print("[green]Database initialized successfully.[/green]")


@app.command()
def discover(
    industry: str = typer.Argument(..., help="Industry to search, for example: hotel, clinic, school, real estate."),
    location: Optional[str] = typer.Option(None, "--location", "-l", help="Target location, for example: Akure, Lagos, Abuja."),
    keywords: Optional[str] = typer.Option(None, "--keywords", "-k", help="Extra search keywords, for example: booking, appointment, services."),
    limit: int = typer.Option(10, "--limit", help="Maximum candidate websites to discover."),
    save: bool = typer.Option(False, "--save", help="Audit and save discovered websites as leads."),
):
    """Discover possible business websites from industry and location."""
    discovery = LeadDiscovery()

    try:
        candidates = discovery.discover(
            industry=industry,
            location=location or "",
            keywords=keywords or "",
            max_results=limit,
        )
    except Exception as exc:
        console.print(f"[red]Discovery failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not candidates:
        console.print("[yellow]No candidate websites found. Try a broader industry/location keyword.[/yellow]")
        return

    table = Table(title="Discovered Lead Candidates")
    table.add_column("#", justify="right")
    table.add_column("Business")
    table.add_column("Website")
    table.add_column("Query")

    for index, candidate in enumerate(candidates, start=1):
        table.add_row(
            str(index),
            candidate.business_name,
            candidate.website,
            candidate.search_query,
        )

    console.print(table)

    if not save:
        console.print("[bold cyan]Tip:[/bold cyan] Add --save to audit and save these candidates as leads.")
        return

    auditor = WebsiteAuditor()
    saved = 0

    for candidate in candidates:
        console.print(f"[cyan]Auditing[/cyan] {candidate.website}")

        try:
            audit = auditor.audit(candidate.website)
            lead_id = save_lead(
                audit,
                business_name=candidate.business_name,
                industry=candidate.industry,
                source=candidate.source,
                location=candidate.location,
                status="new",
                notes=f"Discovered from query: {candidate.search_query}",
            )
        except Exception as exc:
            console.print(f"[red]Skipped {candidate.website}: {exc}[/red]")
            continue

        saved += 1
        console.print(f"[green]Saved lead #{lead_id}[/green] | Score: {audit.opportunity_score}/100")

    console.print(f"[bold green]Done. Saved {saved} discovered lead(s).[/bold green]")


@app.command()
def scan(
    url: str,
    business_name: Optional[str] = typer.Option(None, "--business-name", "-b"),
    industry: Optional[str] = typer.Option(None, "--industry", "-i"),
    source: Optional[str] = typer.Option(None, "--source", "-s"),
    contact_name: Optional[str] = typer.Option(None, "--contact-name"),
    contact_email: Optional[str] = typer.Option(None, "--contact-email"),
    phone: Optional[str] = typer.Option(None, "--phone"),
    location: Optional[str] = typer.Option(None, "--location"),
    status: str = typer.Option("new", "--status", help="Lead status: new, contacted, replied, won, lost."),
    notes: Optional[str] = typer.Option(None, "--notes", help="Optional internal notes about this lead."),
):
    """Audit one website and save it as a lead."""
    auditor = WebsiteAuditor()
    audit = auditor.audit(url)

    try:
        lead_id = save_lead(
            audit,
            business_name=business_name,
            industry=industry,
            source=source,
            contact_name=contact_name,
            contact_email=contact_email,
            phone=phone,
            location=location,
            status=status,
            notes=notes,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    show_audit(audit.to_dict(), lead_id)


@app.command()
def bulk(csv_file: Path):
    """Bulk audit websites from a CSV file."""
    if not csv_file.exists():
        raise typer.BadParameter(f"CSV file not found: {csv_file}")

    auditor = WebsiteAuditor()
    total = 0

    with csv_file.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            website = row.get("website") or row.get("url")

            if not website:
                console.print("[yellow]Skipping row without website/url.[/yellow]")
                continue

            console.print(f"[cyan]Scanning[/cyan] {website}")
            audit = auditor.audit(website)

            try:
                lead_id = save_lead(
                    audit,
                    business_name=row.get("business_name"),
                    industry=row.get("industry"),
                    source=row.get("source"),
                    contact_name=row.get("contact_name"),
                    contact_email=row.get("contact_email"),
                    phone=row.get("phone"),
                    location=row.get("location"),
                    status=row.get("status") or "new",
                    notes=row.get("notes"),
                )
            except ValueError as exc:
                console.print(f"[red]Skipping {website}: {exc}[/red]")
                continue

            console.print(f"[green]Saved lead #{lead_id}[/green] | Score: {audit.opportunity_score}/100")
            total += 1

    console.print(f"[bold green]Done. Scanned {total} lead(s).[/bold green]")


@app.command(name="leads")
def leads(limit: int = typer.Option(20, "--limit", "-l")):
    """Show recently saved leads."""
    rows = list_leads(limit=limit)

    table = Table(title="Wireless Bot Leads")
    table.add_column("ID", justify="right")
    table.add_column("Business")
    table.add_column("Website")
    table.add_column("Industry")
    table.add_column("Status")
    table.add_column("Score", justify="right")
    table.add_column("Footer Year", justify="right")
    table.add_column("Stale?", justify="center")
    table.add_column("Created")

    for row in rows:
        table.add_row(
            str(row["id"]),
            row["business_name"] or "-",
            row["website"],
            row["industry"] or "-",
            row["status"] or "new",
            str(row["opportunity_score"] or 0),
            str(row["footer_year"] or "-"),
            "Yes" if row["stale_footer"] else "No",
            row["created_at"],
        )

    console.print(table)


@app.command(name="delete")
def delete_command(
    lead_id: int = typer.Argument(..., help="ID of the lead to delete."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Delete without confirmation."),
):
    """Delete a saved lead permanently."""
    lead = get_lead(lead_id)

    if not lead:
        console.print(f"[red]Lead #{lead_id} not found.[/red]")
        raise typer.Exit(code=1)

    if not yes:
        confirmed = typer.confirm(
            f"Delete lead #{lead_id} ({lead['business_name'] or lead['website']}) permanently?"
        )
        if not confirmed:
            console.print("[yellow]Delete cancelled.[/yellow]")
            return

    if delete_lead(lead_id):
        console.print(f"[green]Lead #{lead_id} deleted.[/green]")
    else:
        console.print(f"[red]Lead #{lead_id} could not be deleted.[/red]")
        raise typer.Exit(code=1)


@app.command(name="status")
def status_command(
    lead_id: int,
    status: str = typer.Argument(..., help="One of: new, contacted, replied, won, lost."),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Optional internal notes to save with this status update."),
):
    """Update a lead's pipeline status."""
    try:
        lead = update_lead_status(lead_id, status, notes=notes)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        console.print(f"Allowed statuses: {', '.join(VALID_LEAD_STATUSES)}")
        raise typer.Exit(code=1) from exc

    if not lead:
        console.print(f"[red]Lead #{lead_id} not found.[/red]")
        raise typer.Exit(code=1)

    console.print(
        f"[green]Lead #{lead_id} status updated to '{lead['status']}'.[/green]"
    )

    if lead["notes"]:
        console.print(Panel(lead["notes"], title="Notes", expand=False))


@app.command()
def pitch(lead_id: int):
    """Generate email, WhatsApp message, and proposal for a saved lead."""
    lead = get_lead(lead_id)

    if not lead:
        console.print(f"[red]Lead #{lead_id} not found.[/red]")
        raise typer.Exit(code=1)

    outreach = build_outreach(lead)

    console.print(Panel(outreach["email"], title="Email Pitch", expand=False))
    console.print(Panel(outreach["whatsapp"], title="WhatsApp Pitch", expand=False))
    console.print(Panel(outreach["proposal"], title="Mini Proposal", expand=False))


@app.command()
def export():
    """Export all leads to CSV."""
    output_path = export_leads()
    console.print(f"[green]Exported leads to:[/green] {output_path}")


def show_audit(audit: dict, lead_id: int):
    table = Table(title=f"Audit Result | Lead #{lead_id}")
    table.add_column("Signal")
    table.add_column("Value")

    main_fields = [
        "url",
        "final_url",
        "status_code",
        "response_time_ms",
        "page_size_kb",
        "title",
        "meta_description",
        "detected_platform",
        "footer_year",
        "stale_footer",
        "https_enabled",
        "has_viewport",
        "has_sitemap",
        "has_robots",
        "opportunity_score",
    ]

    for field in main_fields:
        table.add_row(field, str(audit.get(field)))

    console.print(table)

    issues = audit.get("issues", [])
    recommendations = audit.get("recommendations", [])

    console.print(Panel("\n".join(f"- {item}" for item in issues) or "No major issues found.", title="Issues"))
    console.print(Panel("\n".join(f"- {item}" for item in recommendations) or "No recommendations.", title="Recommendations"))
    console.print(f"[bold cyan]Next:[/bold cyan] python -m clienthunter.cli pitch {lead_id}")
    console.print(f"[bold cyan]Track:[/bold cyan] python -m clienthunter.cli status {lead_id} contacted --notes \"Sent first message\"")


if __name__ == "__main__":
    app()
