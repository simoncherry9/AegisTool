"""CLI del módulo de descubrimiento (minuta §14, §37).

Comandos:
  discovery scan      — iniciar escaneo
  discovery stop      — detener escaneo
  discovery status    — estado del escaneo
  discovery aps       — listar APs
  discovery clients   — listar clientes
  discovery export    — exportar inventario
  discovery degraded  — APs con seguridad degradada
  discovery channel   — cambiar canal
"""

from __future__ import annotations

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from aegiswifi.discovery import service as discovery_service
from aegiswifi.discovery.schemas import (
    ScanConfig,
)

discovery_app = typer.Typer(name="discovery", help="Descubrimiento inalámbrico")
console = Console()


@discovery_app.command()
def scan(
    interface: str = typer.Argument(..., help="Interfaz en monitor mode"),
    channel: int | None = typer.Option(None, "--channel", "-c", help="Canal fijo"),
    watch: bool = typer.Option(False, "--watch", "-w", help="Live watch"),
) -> None:
    """Inicia un escaneo de descubrimiento."""
    import asyncio

    config = ScanConfig(interface=interface, channel=channel)
    status = asyncio.run(discovery_service.start_scan(config))

    if status.error:
        console.print(f"[red]Error:[/red] {status.error}")
        raise typer.Exit(1)

    console.print(f"[green]Escaneo iniciado en {interface}[/green]")

    if watch:
        _watch_loop()


@discovery_app.command()
def stop() -> None:
    """Detiene el escaneo activo."""
    import asyncio

    status = asyncio.run(discovery_service.stop_scan())
    if status.running:
        console.print("[red]No se pudo detener el escaneo[/red]")
    else:
        console.print("[green]Escaneo detenido[/green]")


@discovery_app.command()
def status() -> None:
    """Muestra el estado del escaneo activo."""
    import asyncio

    s = asyncio.run(discovery_service.get_scan_status())

    if not s.running:
        console.print("[yellow]No hay escaneo activo[/yellow]")
        return

    table = Table(title="Estado del Escaneo", box=box.ROUNDED)
    table.add_column("Campo", style="bold")
    table.add_column("Valor")

    table.add_row("Interfaz", s.interface or "-")
    table.add_row("Canal", str(s.channel) if s.channel else "Hopping")
    table.add_row("APs", str(s.ap_count))
    table.add_row("Clientes", str(s.client_count))
    table.add_row("Tiempo", f"{s.uptime_seconds}s" if s.uptime_seconds else "-")
    table.add_row("Error", f"[red]{s.error}[/red]" if s.error else "[green]OK[/green]")

    console.print(table)


@discovery_app.command()
def aps(
    protocol: str | None = typer.Option(None, "--protocol", "-p", help="Filtrar por protocolo"),
    wps: bool | None = typer.Option(None, "--wps", help="Solo con WPS"),
    degraded: bool = typer.Option(False, "--degraded", "-d", help="Solo degradados"),
) -> None:
    """Lista Access Points descubiertos."""
    import asyncio

    if degraded:
        ap_list = asyncio.run(discovery_service.find_degraded_aps())
    else:
        from aegiswifi.discovery.schemas import InventoryFilter

        filters = None
        if protocol or wps is not None:
            filters = InventoryFilter(
                protocol=protocol,
                wps=wps,
            )
        ap_list = asyncio.run(discovery_service.list_aps(filters))

    if not ap_list:
        console.print("[yellow]No se encontraron APs[/yellow]")
        return

    table = Table(title=f"APs ({len(ap_list)})", box=box.ROUNDED)
    table.add_column("BSSID", style="cyan")
    table.add_column("SSID", style="bold")
    table.add_column("Ch", justify="center")
    table.add_column("Señal", justify="right")
    table.add_column("Protocolo")
    table.add_column("WPS", justify="center")
    table.add_column("PMF")
    table.add_column("Degr.", justify="center")

    for ap in ap_list:
        table.add_row(
            ap.bssid,
            ap.ssid or "-",
            str(ap.channel) if ap.channel else "-",
            f"{ap.signal} dBm" if ap.signal is not None else "-",
            str(ap.protocol),
            "[green]✓[/green]" if ap.wps else "[dim]—[/dim]",
            str(ap.pmf),
            "[red]✓[/red]" if ap.degraded else "[dim]—[/dim]",
        )

    console.print(table)


@discovery_app.command()
def clients() -> None:
    """Lista clientes descubiertos."""
    import asyncio

    client_list = asyncio.run(discovery_service.list_clients())

    if not client_list:
        console.print("[yellow]No se encontraron clientes[/yellow]")
        return

    table = Table(title=f"Clientes ({len(client_list)})", box=box.ROUNDED)
    table.add_column("MAC", style="cyan")
    table.add_column("Señal", justify="right")
    table.add_column("BSSID Asoc.")
    table.add_column("Probes")

    for c in client_list:
        probes = ", ".join(c.probe_requests[:3]) if c.probe_requests else "-"
        if len(c.probe_requests) > 3:
            probes += "…"

        table.add_row(
            c.mac,
            f"{c.signal} dBm" if c.signal is not None else "-",
            c.associated_bssid or "-",
            probes,
        )

    console.print(table)


@discovery_app.command()
def export(
    output: str = typer.Argument("inventory.json", help="Archivo de salida"),
    protocol: str | None = typer.Option(None, "--protocol", "-p"),
) -> None:
    """Exporta el inventario a JSON."""
    import asyncio
    from pathlib import Path

    from aegiswifi.discovery.schemas import InventoryFilter

    filters = InventoryFilter(protocol=protocol) if protocol else None
    exported = asyncio.run(discovery_service.export_inventory(filters))

    path = Path(output)
    path.write_text(exported.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"[green]Inventario exportado a {path}[/green] ({len(exported.access_points)} APs, {len(exported.clients)} clientes)")


@discovery_app.command()
def degraded() -> None:
    """Muestra APs con seguridad degradada."""
    import asyncio

    ap_list = asyncio.run(discovery_service.find_degraded_aps())

    if not ap_list:
        console.print("[green]No hay APs con seguridad degradada[/green]")
        return

    table = Table(title=f"APs Degradados ({len(ap_list)})", box=box.ROUNDED)
    table.add_column("BSSID", style="cyan")
    table.add_column("SSID", style="bold")
    table.add_column("Protocolo")
    table.add_column("Degr.", justify="center")

    for ap in ap_list:
        table.add_row(
            ap.bssid,
            ap.ssid or "-",
            str(ap.protocol),
            "[red]✓[/red]",
        )

    console.print(table)


@discovery_app.command()
def channel(
    channel: int = typer.Argument(..., help="Nuevo canal (1-14, 36-165)"),
) -> None:
    """Cambia el canal del escaneo activo."""
    import asyncio

    status = asyncio.run(discovery_service.set_scan_channel(channel))

    if status.error:
        console.print(f"[red]Error:[/red] {status.error}")
        raise typer.Exit(1)

    console.print(f"[green]Canal cambiado a {channel}[/green]")


# ── Helpers ────────────────────────────────────────────────────────


def _watch_loop() -> None:
    """Loop de monitoreo en vivo."""
    import asyncio
    import time

    try:
        while True:
            s = asyncio.run(discovery_service.get_scan_status())
            console.clear()
            console.print(f"[bold]Escaneando en {s.interface}[/bold] | Canal: {s.channel or 'Hopping'} | APs: {s.ap_count} | Clients: {s.client_count} | Tiempo: {s.uptime_seconds}s")
            time.sleep(2)
    except KeyboardInterrupt:
        console.print("\n[yellow]Watch detenido[/yellow]")