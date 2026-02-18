#!/usr/bin/env python3
# OS: Ubuntu with Ollama/CodeLlama integration
# Setup: pip install httpx asyncio websockets rich ollama
# Run: python unified_ollama_client.py
# This integrates Ollama LLM with both AutoCAD and ETABS clients

import asyncio
import httpx
import json
import re
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
import logging

# Try to import ollama
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("Warning: ollama not installed. Install with: pip install ollama")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WINDOWS_SERVER = "192.168.1.193"
AUTOCAD_BASE = f"http://{WINDOWS_SERVER}:8000"
ETABS_BASE = f"http://{WINDOWS_SERVER}:8001"

console = Console()

class AutoCADClient:
    """AutoCAD client for communication with Windows server"""
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.connected = False
        
    async def connect_http(self) -> Dict[str, Any]:
        try:
            response = await self.http_client.post(f"{AUTOCAD_BASE}/connect")
            response.raise_for_status()
            self.connected = True
            return response.json()
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def new_drawing(self) -> Dict[str, Any]:
        response = await self.http_client.post(f"{AUTOCAD_BASE}/new_drawing")
        response.raise_for_status()
        return response.json()
    
    async def draw_line(self, start: List[float], end: List[float]) -> Dict[str, Any]:
        response = await self.http_client.post(
            f"{AUTOCAD_BASE}/draw_line",
            json={"start": start, "end": end}
        )
        response.raise_for_status()
        return response.json()
    
    async def draw_circle(self, center: List[float], radius: float) -> Dict[str, Any]:
        response = await self.http_client.post(
            f"{AUTOCAD_BASE}/draw_circle",
            json={"center": center, "radius": radius}
        )
        response.raise_for_status()
        return response.json()
    
    async def create_building_2d(self, length: float, width: float, 
                                 bay_spacing: float = 6.0) -> Dict[str, Any]:
        response = await self.http_client.post(
            f"{AUTOCAD_BASE}/create_building_2d",
            json={"length": length, "width": width, "bay_spacing": bay_spacing}
        )
        response.raise_for_status()
        return response.json()
    
    async def create_building_3d(self, floors: int, length: float, width: float,
                                 bay_spacing: float = 6.0, 
                                 floor_height: float = 3.5) -> Dict[str, Any]:
        response = await self.http_client.post(
            f"{AUTOCAD_BASE}/create_building_3d",
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
            f"{AUTOCAD_BASE}/save_drawing",
            json={"filename": filename}
        )
        response.raise_for_status()
        return response.json()
    
    async def zoom_extents(self) -> Dict[str, Any]:
        response = await self.http_client.post(f"{AUTOCAD_BASE}/zoom_extents")
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        await self.http_client.aclose()

class ETABSClient:
    """ETABS client for communication with Windows server"""
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.connected = False
        
    async def connect(self) -> Dict[str, Any]:
        try:
            response = await self.http_client.post(f"{ETABS_BASE}/connect")
            response.raise_for_status()
            self.connected = True
            return response.json()
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def get_units(self) -> Dict[str, Any]:
        response = await self.http_client.get(f"{ETABS_BASE}/units")
        response.raise_for_status()
        return response.json()
    
    async def create_objects(self, objects: List[Dict[str, Any]]) -> Dict[str, Any]:
        response = await self.http_client.post(
            f"{ETABS_BASE}/create_objects",
            json={"objects": objects}
        )
        response.raise_for_status()
        return response.json()
    
    async def create_frame_structure(self, floors: int, length: float, width: float,
                                    bay_spacing: float = 6.0, 
                                    floor_height: float = 3.5) -> Dict[str, Any]:
        """Create a structural frame in ETABS"""
        objects = []
        
        # Calculate grid points
        nx = int(length / bay_spacing) + 1
        ny = int(width / bay_spacing) + 1
        
        # Create columns (vertical lines)
        for i in range(nx):
            x = i * bay_spacing
            for j in range(ny):
                y = j * bay_spacing
                for k in range(floors + 1):
                    z = k * floor_height
                    if k < floors:
                        # Column from this floor to next
                        objects.append({
                            "type": "line",
                            "xs": [x, x],
                            "ys": [y, y],
                            "zs": [z, z + floor_height],
                            "id": f"COL_{i}_{j}_{k}"
                        })
        
        # Create beams (horizontal lines) at each floor
        for k in range(1, floors + 1):
            z = k * floor_height
            
            # X-direction beams
            for i in range(nx - 1):
                x1 = i * bay_spacing
                x2 = (i + 1) * bay_spacing
                for j in range(ny):
                    y = j * bay_spacing
                    objects.append({
                        "type": "line",
                        "xs": [x1, x2],
                        "ys": [y, y],
                        "zs": [z, z],
                        "id": f"BEAM_X_{i}_{j}_{k}"
                    })
            
            # Y-direction beams
            for i in range(nx):
                x = i * bay_spacing
                for j in range(ny - 1):
                    y1 = j * bay_spacing
                    y2 = (j + 1) * bay_spacing
                    objects.append({
                        "type": "line",
                        "xs": [x, x],
                        "ys": [y1, y2],
                        "zs": [z, z],
                        "id": f"BEAM_Y_{i}_{j}_{k}"
                    })
            
            # Create floor slabs (area elements)
            for i in range(nx - 1):
                x1 = i * bay_spacing
                x2 = (i + 1) * bay_spacing
                for j in range(ny - 1):
                    y1 = j * bay_spacing
                    y2 = (j + 1) * bay_spacing
                    objects.append({
                        "type": "area",
                        "xs": [x1, x2, x2, x1],
                        "ys": [y1, y1, y2, y2],
                        "zs": [z, z, z, z],
                        "id": f"SLAB_{i}_{j}_{k}"
                    })
        
        return await self.create_objects(objects)
    
    async def close(self):
        await self.http_client.aclose()

class UnifiedCADInterpreter:
    """Unified interpreter for both AutoCAD and ETABS with Ollama/LLM"""
    
    def __init__(self, model="codellama:34b"):
        self.model = model
        self.autocad_client = AutoCADClient()
        self.etabs_client = ETABSClient()
        self.current_app = None  # Track which app is active
        
    async def process_with_llm(self, prompt: str) -> Dict[str, Any]:
        """Process natural language with CodeLlama"""
        
        system_message = """You are a CAD assistant for both AutoCAD and ETABS. Convert natural language to JSON commands.

Available commands:

AutoCAD commands:
- 3D Building: {"app": "autocad", "action": "building_3d", "floors": N, "length": X, "width": Y, "floor_height": H}
- 2D Building: {"app": "autocad", "action": "building_2d", "length": X, "width": Y}
- Line: {"app": "autocad", "action": "line", "start": [x1,y1,z1], "end": [x2,y2,z2]}
- Circle: {"app": "autocad", "action": "circle", "center": [x,y,z], "radius": R}

ETABS commands:
- Structural Frame: {"app": "etabs", "action": "frame", "floors": N, "length": X, "width": Y, "floor_height": H}
- Column: {"app": "etabs", "action": "column", "x": X, "y": Y, "height": H}
- Beam: {"app": "etabs", "action": "beam", "start": [x1,y1,z1], "end": [x2,y2,z2]}
- Slab: {"app": "etabs", "action": "slab", "points": [[x1,y1,z1], [x2,y2,z2], ...]}

Rules:
- If user mentions "structure", "frame", "analysis", "column", "beam", "slab" -> use ETABS
- If user mentions "drawing", "visual", "3d building", "2d plan", "circle" -> use AutoCAD
- Default to the last used app if unclear

Respond ONLY with JSON."""

        if OLLAMA_AVAILABLE:
            try:
                client = ollama.Client()
                response = client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt}
                    ]
                )
                
                llm_output = response['message']['content']
                return self._parse_llm_response(llm_output)
                
            except Exception as e:
                console.print(f"[yellow]Ollama error: {e}. Using pattern matching.[/yellow]")
                return self._parse_without_llm(prompt)
        else:
            return self._parse_without_llm(prompt)
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Extract JSON from LLM response"""
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            return json.loads(response)
        except:
            match = re.search(r'\{[^}]+\}', response)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
            
            return {"action": "unknown", "error": "Failed to parse LLM response"}
    
    def _parse_without_llm(self, prompt: str) -> Dict[str, Any]:
        """Parse without LLM using patterns"""
        prompt_lower = prompt.lower()
        
        # Detect which app to use
        etabs_keywords = ['structure', 'structural', 'frame', 'column', 'beam', 'slab', 'etabs', 'analysis']
        autocad_keywords = ['drawing', 'visual', 'autocad', 'circle', 'line']
        
        use_etabs = any(keyword in prompt_lower for keyword in etabs_keywords)
        use_autocad = any(keyword in prompt_lower for keyword in autocad_keywords)
        
        # Default to last used app or AutoCAD
        if not use_etabs and not use_autocad:
            use_autocad = True if self.current_app != "etabs" else False
            use_etabs = not use_autocad
        
        # Extract numbers
        numbers = re.findall(r'\d+(?:\.\d+)?', prompt)
        
        # Building/Structure detection
        if any(word in prompt_lower for word in ['building', 'structure', 'tower', 'frame']):
            result = {
                "app": "etabs" if use_etabs else "autocad",
                "action": "frame" if use_etabs else "building_3d",
                "floors": 1,
                "length": 30,
                "width": 20,
                "floor_height": 3.5
            }
            
            # Extract dimensions
            dim_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:m|meters?)?\s*(?:by|x)\s*(\d+(?:\.\d+)?)', prompt_lower)
            if dim_match:
                result["length"] = float(dim_match.group(1))
                result["width"] = float(dim_match.group(2))
            elif numbers and len(numbers) >= 2:
                result["length"] = float(numbers[0])
                result["width"] = float(numbers[1])
            
            # Extract floors
            floor_match = re.search(r'(\d+)\s*(?:floor|story|storey)', prompt_lower)
            if floor_match:
                result["floors"] = int(floor_match.group(1))
            
            # Extract height
            height_match = re.search(r'(\d+(?:\.\d+)?)\s*m(?:eter)?\s*(?:height|tall|floor\s*height)', prompt_lower)
            if height_match:
                result["floor_height"] = float(height_match.group(1))
            
            # Check if 2D (AutoCAD only)
            if '2d' in prompt_lower or 'plan' in prompt_lower:
                result["app"] = "autocad"
                result["action"] = "building_2d"
                del result["floors"]
                del result["floor_height"]
            
            return result
        
        # Column detection (ETABS)
        elif 'column' in prompt_lower:
            result = {"app": "etabs", "action": "column", "x": 0, "y": 0, "height": 3.5}
            if numbers:
                if len(numbers) >= 3:
                    result["x"] = float(numbers[0])
                    result["y"] = float(numbers[1])
                    result["height"] = float(numbers[2])
                elif len(numbers) == 1:
                    result["height"] = float(numbers[0])
            return result
        
        # Beam detection (ETABS)
        elif 'beam' in prompt_lower:
            result = {
                "app": "etabs",
                "action": "beam",
                "start": [0, 0, 3.5],
                "end": [6, 0, 3.5]
            }
            if numbers and len(numbers) >= 4:
                result["start"] = [float(numbers[0]), float(numbers[1]), 3.5]
                result["end"] = [float(numbers[2]), float(numbers[3]), 3.5]
            return result
        
        # Line detection (AutoCAD)
        elif 'line' in prompt_lower:
            result = {"app": "autocad", "action": "line", "start": [0, 0, 0], "end": [10, 10, 0]}
            if numbers and len(numbers) >= 2:
                result["end"] = [float(numbers[0]), float(numbers[1]), 0]
            if len(numbers) >= 4:
                result["start"] = [float(numbers[0]), float(numbers[1]), 0]
                result["end"] = [float(numbers[2]), float(numbers[3]), 0]
            return result
        
        # Circle detection (AutoCAD)
        elif 'circle' in prompt_lower:
            result = {"app": "autocad", "action": "circle", "center": [0, 0, 0], "radius": 5}
            if numbers:
                result["radius"] = float(numbers[-1])
                if len(numbers) >= 3:
                    result["center"] = [float(numbers[0]), float(numbers[1]), 0]
            return result
        
        return {"action": "unknown", "error": "Could not parse command"}
    
    async def execute_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Execute parsed command on appropriate application"""
        app = command.get("app")
        action = command.get("action")
        
        try:
            if app == "autocad":
                self.current_app = "autocad"
                
                if action == "building_3d":
                    result = await self.autocad_client.create_building_3d(
                        floors=command.get("floors", 1),
                        length=command.get("length", 30),
                        width=command.get("width", 20),
                        floor_height=command.get("floor_height", 3.5)
                    )
                    console.print(f"[green]AutoCAD: Created 3D building[/green]")
                    
                elif action == "building_2d":
                    result = await self.autocad_client.create_building_2d(
                        length=command.get("length", 30),
                        width=command.get("width", 20)
                    )
                    console.print(f"[green]AutoCAD: Created 2D plan[/green]")
                    
                elif action == "line":
                    result = await self.autocad_client.draw_line(
                        start=command.get("start", [0, 0, 0]),
                        end=command.get("end", [10, 10, 0])
                    )
                    console.print(f"[green]AutoCAD: Drew line[/green]")
                    
                elif action == "circle":
                    result = await self.autocad_client.draw_circle(
                        center=command.get("center", [0, 0, 0]),
                        radius=command.get("radius", 5)
                    )
                    console.print(f"[green]AutoCAD: Drew circle[/green]")
                
            elif app == "etabs":
                self.current_app = "etabs"
                
                if action == "frame":
                    result = await self.etabs_client.create_frame_structure(
                        floors=command.get("floors", 1),
                        length=command.get("length", 30),
                        width=command.get("width", 20),
                        floor_height=command.get("floor_height", 3.5)
                    )
                    console.print(f"[green]ETABS: Created structural frame[/green]")
                    
                elif action == "column":
                    objects = [{
                        "type": "line",
                        "xs": [command.get("x", 0), command.get("x", 0)],
                        "ys": [command.get("y", 0), command.get("y", 0)],
                        "zs": [0, command.get("height", 3.5)]
                    }]
                    result = await self.etabs_client.create_objects(objects)
                    console.print(f"[green]ETABS: Created column[/green]")
                    
                elif action == "beam":
                    start = command.get("start", [0, 0, 3.5])
                    end = command.get("end", [6, 0, 3.5])
                    objects = [{
                        "type": "line",
                        "xs": [start[0], end[0]],
                        "ys": [start[1], end[1]],
                        "zs": [start[2], end[2]]
                    }]
                    result = await self.etabs_client.create_objects(objects)
                    console.print(f"[green]ETABS: Created beam[/green]")
            
            else:
                result = {"success": False, "message": f"Unknown app: {app}"}
                console.print(f"[red]Unknown application[/red]")
            
            return result
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return {"success": False, "message": str(e)}

class UnifiedCADClient:
    """Main unified client with Ollama integration for both AutoCAD and ETABS"""
    
    def __init__(self):
        self.interpreter = UnifiedCADInterpreter()
        self.autocad_connected = False
        self.etabs_connected = False
        
    async def check_servers(self):
        """Check availability of both servers"""
        console.print("\n[yellow]Checking server availability...[/yellow]")
        
        # Check AutoCAD
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{AUTOCAD_BASE}/health", timeout=2.0)
                if response.status_code == 200:
                    console.print(f"[green]✓ AutoCAD server available at {WINDOWS_SERVER}:8000[/green]")
                    self.autocad_available = True
                else:
                    console.print(f"[yellow]⚠ AutoCAD server responding but not ready[/yellow]")
                    self.autocad_available = False
        except:
            console.print(f"[red]✗ AutoCAD server not available[/red]")
            self.autocad_available = False
        
        # Check ETABS
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{ETABS_BASE}/health", timeout=2.0)
                if response.status_code == 200:
                    console.print(f"[green]✓ ETABS server available at {WINDOWS_SERVER}:8001[/green]")
                    self.etabs_available = True
                else:
                    console.print(f"[yellow]⚠ ETABS server responding but not ready[/yellow]")
                    self.etabs_available = False
        except:
            console.print(f"[red]✗ ETABS server not available[/red]")
            self.etabs_available = False
    
    async def connect_services(self):
        """Connect to available services"""
        console.print("\n[yellow]Connecting to services...[/yellow]")
        
        if self.autocad_available:
            result = await self.interpreter.autocad_client.connect_http()
            if result.get("success"):
                console.print("[green]✓ Connected to AutoCAD[/green]")
                await self.interpreter.autocad_client.new_drawing()
                self.autocad_connected = True
            else:
                console.print(f"[red]✗ AutoCAD connection failed: {result.get('message')}[/red]")
                self.autocad_connected = False
        
        if self.etabs_available:
            result = await self.interpreter.etabs_client.connect()
            if result.get("success"):
                console.print("[green]✓ Connected to ETABS[/green]")
                units = await self.interpreter.etabs_client.get_units()
                console.print(f"[cyan]  ETABS Units: {units.get('units', 'Unknown')}[/cyan]")
                self.etabs_connected = True
            else:
                console.print(f"[red]✗ ETABS connection failed: {result.get('message')}[/red]")
                self.etabs_connected = False
    
    def show_status(self):
        """Show connection status"""
        table = Table(title="Connection Status")
        table.add_column("Service", style="cyan")
        table.add_column("Server", style="yellow")
        table.add_column("Port", style="yellow")
        table.add_column("Status", style="green")
        
        autocad_status = "✓ Connected" if self.autocad_connected else "✗ Not Connected"
        etabs_status = "✓ Connected" if self.etabs_connected else "✗ Not Connected"
        
        table.add_row("AutoCAD", WINDOWS_SERVER, "8000", autocad_status)
        table.add_row("ETABS", WINDOWS_SERVER, "8001", etabs_status)
        
        console.print(table)
    
    async def run(self):
        """Run the unified client"""
        console.print(Panel.fit(
            "[bold cyan]Unified CAD Client with Ollama/CodeLlama[/bold cyan]\n" +
            "Supports: AutoCAD + ETABS\n" +
            f"LLM: {'Available' if OLLAMA_AVAILABLE else 'Not Available (using patterns)'}",
            title="CAD + AI Integration"
        ))
        
        # Check and connect to servers
        await self.check_servers()
        await self.connect_services()
        self.show_status()
        
        if not self.autocad_connected and not self.etabs_connected:
            console.print("\n[red]No services available. Please start the servers first.[/red]")
            return
        
        # Show examples
        console.print("\n[bold]Example commands:[/bold]")
        
        if self.autocad_connected:
            console.print("\n[cyan]AutoCAD:[/cyan]")
            console.print("  • create a 3d building 40m by 40m with 5 floors")
            console.print("  • draw a 2d floor plan 25x35")
            console.print("  • draw a circle with radius 15")
        
        if self.etabs_connected:
            console.print("\n[cyan]ETABS:[/cyan]")
            console.print("  • create structural frame 50x30 with 8 floors")
            console.print("  • add a column at position 10,10 with height 4m")
            console.print("  • create a beam from 0,0,3.5 to 6,0,3.5")
        
        console.print("\n[bold]Other commands:[/bold] status, switch, save, exit")
        
        # Main loop
        while True:
            try:
                user_input = console.input("\n[cyan]Enter command: [/cyan]")
                
                if user_input.lower() in ['exit', 'quit', 'q']:
                    break
                
                elif user_input.lower() == 'status':
                    self.show_status()
                
                elif user_input.lower() == 'switch':
                    if self.interpreter.current_app == "autocad":
                        self.interpreter.current_app = "etabs"
                        console.print("[yellow]Switched to ETABS mode[/yellow]")
                    else:
                        self.interpreter.current_app = "autocad"
                        console.print("[yellow]Switched to AutoCAD mode[/yellow]")
                
                elif user_input.lower().startswith('save'):
                    if self.autocad_connected:
                        filename = user_input.replace('save', '').strip() or 'drawing'
                        result = await self.interpreter.autocad_client.save_drawing(filename)
                        console.print(f"[green]AutoCAD: Saved as {filename}.dwg[/green]")
                    else:
                        console.print("[yellow]Save is only available for AutoCAD[/yellow]")
                
                else:
                    # Process with Ollama/patterns
                    console.print("[yellow]Processing...[/yellow]")
                    command = await self.interpreter.process_with_llm(user_input)
                    
                    if command.get("action") != "unknown":
                        # Check if the target app is connected
                        target_app = command.get("app")
                        if target_app == "autocad" and not self.autocad_connected:
                            console.print("[red]AutoCAD is not connected[/red]")
                        elif target_app == "etabs" and not self.etabs_connected:
                            console.print("[red]ETABS is not connected[/red]")
                        else:
                            console.print(f"[cyan]Interpreted as: {command}[/cyan]")
                            await self.interpreter.execute_command(command)
                    else:
                        console.print("[red]Could not understand command. Try being more specific.[/red]")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
        
        # Cleanup
        await self.interpreter.autocad_client.close()
        await self.interpreter.etabs_client.close()
        console.print("[green]Goodbye![/green]")

# Quick test function
async def quick_test():
    """Quick test with predefined commands"""
    client = UnifiedCADClient()
    
    await client.check_servers()
    await client.connect_services()
    
    test_prompts = [
        "create a 3d building 40x40 with 5 floors in autocad",
        "create structural frame 50x30 with 8 floors in etabs",
        "draw a circle with radius 20",
        "add a column at 10,10 with height 4m"
    ]
    
    for prompt in test_prompts:
        console.print(f"\n[bold]Testing:[/bold] {prompt}")
        command = await client.interpreter.process_with_llm(prompt)
        console.print(f"[cyan]Parsed:[/cyan] {command}")
        if command.get("action") != "unknown":
            await client.interpreter.execute_command(command)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        asyncio.run(quick_test())
    else:
        client = UnifiedCADClient()
        asyncio.run(client.run())