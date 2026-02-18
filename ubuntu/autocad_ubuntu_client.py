# OS: Ubuntu (for CodeLlama 34B integration)
# Setup: pip install httpx asyncio websockets rich
# Run: python autocad_ubuntu_client.py
# This connects to Windows server at 192.168.1.193:8000

import asyncio
import httpx
import json
import websockets
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WINDOWS_SERVER = "192.168.1.193"
HTTP_BASE = f"http://{WINDOWS_SERVER}:8000"
WS_BASE = f"ws://{WINDOWS_SERVER}:8000/ws"

console = Console()

class AutoCADClient:
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.ws_connection = None
        self.connected = False
        
    async def connect_http(self) -> Dict[str, Any]:
        try:
            response = await self.http_client.post(f"{HTTP_BASE}/connect")
            response.raise_for_status()
            self.connected = True
            return response.json()
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def new_drawing(self) -> Dict[str, Any]:
        response = await self.http_client.post(f"{HTTP_BASE}/new_drawing")
        response.raise_for_status()
        return response.json()
    
    async def draw_line(self, start: List[float], end: List[float]) -> Dict[str, Any]:
        response = await self.http_client.post(
            f"{HTTP_BASE}/draw_line",
            json={"start": start, "end": end}
        )
        response.raise_for_status()
        return response.json()
    
    async def draw_circle(self, center: List[float], radius: float) -> Dict[str, Any]:
        response = await self.http_client.post(
            f"{HTTP_BASE}/draw_circle",
            json={"center": center, "radius": radius}
        )
        response.raise_for_status()
        return response.json()
    
    async def create_building_2d(self, length: float, width: float, 
                                 bay_spacing: float = 6.0) -> Dict[str, Any]:
        response = await self.http_client.post(
            f"{HTTP_BASE}/create_building_2d",
            json={"length": length, "width": width, "bay_spacing": bay_spacing}
        )
        response.raise_for_status()
        return response.json()
    
    async def create_building_3d(self, floors: int, length: float, width: float,
                                 bay_spacing: float = 6.0, 
                                 floor_height: float = 3.5) -> Dict[str, Any]:
        response = await self.http_client.post(
            f"{HTTP_BASE}/create_building_3d",
            json={
                "floors": floors,
                "length": length,
                "width": width,
                "bay_spacing": bay_spacing,
                "floor_height": floor_height
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def save_drawing(self, filename: str) -> Dict[str, Any]:
        response = await self.http_client.post(
            f"{HTTP_BASE}/save_drawing",
            json={"filename": filename}
        )
        response.raise_for_status()
        return response.json()
    
    async def zoom_extents(self) -> Dict[str, Any]:
        response = await self.http_client.post(f"{HTTP_BASE}/zoom_extents")
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        await self.http_client.aclose()
        if self.ws_connection:
            await self.ws_connection.close()

class InteractiveCLI:
    def __init__(self):
        self.client = AutoCADClient()
        
    async def run(self):
        console.print(Panel.fit(
            "[bold cyan]AutoCAD Remote Control for Ubuntu[/bold cyan]\n" +
            f"Server: {WINDOWS_SERVER}:8000",
            title="AutoCAD Client"
        ))
        
        console.print("\n[yellow]Connecting to AutoCAD server...[/yellow]")
        result = await self.client.connect_http()
        
        if result.get("success"):
            console.print("[green][OK] Connected to AutoCAD[/green]")
        else:
            console.print(f"[red][FAIL] Connection failed: {result.get('message')}[/red]")
            return
        
        while True:
            console.print("\n[bold]Commands:[/bold]")
            console.print("1. New Drawing")
            console.print("2. Draw Line")
            console.print("3. Draw Circle")
            console.print("4. Create 2D Building")
            console.print("5. Create 3D Building")
            console.print("6. Save Drawing")
            console.print("7. Zoom Extents")
            console.print("8. Exit")
            
            choice = console.input("\n[cyan]Select option: [/cyan]")
            
            try:
                if choice == "1":
                    result = await self.client.new_drawing()
                    self._show_result(result)
                    
                elif choice == "2":
                    start_x = float(console.input("Start X: "))
                    start_y = float(console.input("Start Y: "))
                    end_x = float(console.input("End X: "))
                    end_y = float(console.input("End Y: "))
                    result = await self.client.draw_line(
                        [start_x, start_y, 0], 
                        [end_x, end_y, 0]
                    )
                    self._show_result(result)
                    
                elif choice == "3":
                    center_x = float(console.input("Center X: "))
                    center_y = float(console.input("Center Y: "))
                    radius = float(console.input("Radius: "))
                    result = await self.client.draw_circle(
                        [center_x, center_y, 0], 
                        radius
                    )
                    self._show_result(result)
                    
                elif choice == "4":
                    length = float(console.input("Building Length (m): "))
                    width = float(console.input("Building Width (m): "))
                    bay = float(console.input("Bay Spacing (m) [6]: ") or "6")
                    result = await self.client.create_building_2d(length, width, bay)
                    self._show_result(result)
                    
                elif choice == "5":
                    floors = int(console.input("Number of Floors: "))
                    length = float(console.input("Building Length (m): "))
                    width = float(console.input("Building Width (m): "))
                    bay = float(console.input("Bay Spacing (m) [6]: ") or "6")
                    height = float(console.input("Floor Height (m) [3.5]: ") or "3.5")
                    result = await self.client.create_building_3d(
                        floors, length, width, bay, height
                    )
                    self._show_result(result)
                    
                elif choice == "6":
                    filename = console.input("Filename (without .dwg): ")
                    result = await self.client.save_drawing(filename)
                    self._show_result(result)
                    
                elif choice == "7":
                    result = await self.client.zoom_extents()
                    self._show_result(result)
                    
                elif choice == "8":
                    console.print("[yellow]Closing connection...[/yellow]")
                    await self.client.close()
                    break
                    
                else:
                    console.print("[red]Invalid option[/red]")
                    
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
        
        console.print("[green]Goodbye![/green]")
    
    def _show_result(self, result: Dict[str, Any], title: str = "Result"):
        if result.get("success"):
            console.print(f"[green][OK] {title}: {result.get('message', 'Success')}[/green]")
        else:
            console.print(f"[red][FAIL] {title}: {result.get('message', 'Failed')}[/red]")

class AutoCADAPI:
    def __init__(self):
        self.client = AutoCADClient()
        
    async def __aenter__(self):
        await self.client.connect_http()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()
    
    async def create_building(self, floors=5, length=30, width=20):
        return await self.client.create_building_3d(floors, length, width)

async def example_usage():
    async with AutoCADAPI() as api:
        result = await api.create_building(floors=10, length=40, width=30)
        print(f"Building created: {result}")

if __name__ == "__main__":
    cli = InteractiveCLI()
    asyncio.run(cli.run())
