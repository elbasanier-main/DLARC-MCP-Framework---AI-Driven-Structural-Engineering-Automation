#!/usr/bin/env python3
# OS: Ubuntu with Ollama/CodeLlama integration
# Setup: pip install httpx asyncio websockets rich ollama
# Run: python autocad_ollama_client.py
# This integrates Ollama LLM with AutoCAD client

import asyncio
import httpx
import json
import re
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
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
HTTP_BASE = f"http://{WINDOWS_SERVER}:8000"

console = Console()

class AutoCADClient:
    """Original AutoCAD client from autocad_ubuntu_client.py"""
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
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

class OllamaCADInterpreter:
    """Ollama integration for natural language processing"""
    
    def __init__(self, model="codellama:34b"):
        self.model = model
        self.client = AutoCADClient()
        
    async def process_with_llm(self, prompt: str) -> Dict[str, Any]:
        """Process natural language with CodeLlama"""
        
        # LLM system prompt
        system_message = """You are an AutoCAD assistant. Convert natural language to JSON commands.

Available commands:
- 3D Building: {"action": "building_3d", "floors": N, "length": X, "width": Y, "floor_height": H}
- 2D Building: {"action": "building_2d", "length": X, "width": Y}
- Line: {"action": "line", "start": [x1,y1,z1], "end": [x2,y2,z2]}
- Circle: {"action": "circle", "center": [x,y,z], "radius": R}

Respond ONLY with JSON. Examples:
"building 40m by 40m with 4m height" -> {"action": "building_3d", "floors": 1, "length": 40, "width": 40, "floor_height": 4}
"5 story building 30x25" -> {"action": "building_3d", "floors": 5, "length": 30, "width": 25, "floor_height": 3.5}"""

        if OLLAMA_AVAILABLE:
            try:
                # Use Ollama
                client = ollama.Client()
                response = client.chat(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt}
                    ]
                )
                
                # Parse LLM response
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
            # Clean response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            
            # Parse JSON
            return json.loads(response)
        except:
            # Try to find JSON in response
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
        
        # Extract numbers
        numbers = re.findall(r'\d+(?:\.\d+)?', prompt)
        
        # Building detection
        if any(word in prompt_lower for word in ['building', 'structure', 'tower']):
            # Default values
            result = {
                "action": "building_3d",
                "floors": 1,
                "length": 30,
                "width": 20,
                "floor_height": 3.5
            }
            
            # Extract dimensions (e.g., "40m by 40m" or "40x40")
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
            
            # Check if 2D
            if '2d' in prompt_lower or 'plan' in prompt_lower:
                result["action"] = "building_2d"
                del result["floors"]
                del result["floor_height"]
            
            return result
        
        # Line detection
        elif 'line' in prompt_lower:
            result = {"action": "line", "start": [0, 0, 0], "end": [10, 10, 0]}
            if numbers and len(numbers) >= 2:
                result["end"] = [float(numbers[0]), float(numbers[1]), 0]
            if len(numbers) >= 4:
                result["start"] = [float(numbers[0]), float(numbers[1]), 0]
                result["end"] = [float(numbers[2]), float(numbers[3]), 0]
            return result
        
        # Circle detection
        elif 'circle' in prompt_lower:
            result = {"action": "circle", "center": [0, 0, 0], "radius": 5}
            if numbers:
                result["radius"] = float(numbers[-1])
                if len(numbers) >= 3:
                    result["center"] = [float(numbers[0]), float(numbers[1]), 0]
            return result
        
        return {"action": "unknown", "error": "Could not parse command"}
    
    async def execute_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Execute parsed command"""
        action = command.get("action")
        
        try:
            if action == "building_3d":
                result = await self.client.create_building_3d(
                    floors=command.get("floors", 1),
                    length=command.get("length", 30),
                    width=command.get("width", 20),
                    floor_height=command.get("floor_height", 3.5)
                )
                console.print(f"[green]Created 3D building: {command['length']}m x {command['width']}m x {command['floors']} floors[/green]")
                
            elif action == "building_2d":
                result = await self.client.create_building_2d(
                    length=command.get("length", 30),
                    width=command.get("width", 20)
                )
                console.print(f"[green]Created 2D plan: {command['length']}m x {command['width']}m[/green]")
                
            elif action == "line":
                result = await self.client.draw_line(
                    start=command.get("start", [0, 0, 0]),
                    end=command.get("end", [10, 10, 0])
                )
                console.print(f"[green]Drew line[/green]")
                
            elif action == "circle":
                result = await self.client.draw_circle(
                    center=command.get("center", [0, 0, 0]),
                    radius=command.get("radius", 5)
                )
                console.print(f"[green]Drew circle[/green]")
                
            else:
                result = {"success": False, "message": f"Unknown action: {action}"}
                console.print(f"[red]Unknown command[/red]")
            
            return result
            
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            return {"success": False, "message": str(e)}

class OllamaAutoCADClient:
    """Main client with Ollama integration"""
    
    def __init__(self):
        self.interpreter = OllamaCADInterpreter()
        self.client = self.interpreter.client
        
    async def run(self):
        """Run the client"""
        console.print(Panel.fit(
            "[bold cyan]AutoCAD Client with Ollama/CodeLlama[/bold cyan]\n" +
            f"Server: {WINDOWS_SERVER}:8000\n" +
            f"LLM: {'Available' if OLLAMA_AVAILABLE else 'Not Available (using patterns)'}",
            title="AutoCAD + AI"
        ))
        
        # Connect
        console.print("\n[yellow]Connecting to AutoCAD server...[/yellow]")
        result = await self.client.connect_http()
        
        if result.get("success"):
            console.print("[green]Connected to AutoCAD[/green]")
            await self.client.new_drawing()
            console.print("[green]New drawing created[/green]")
        else:
            console.print(f"[red]Connection failed: {result.get('message')}[/red]")
            return
        
        # Show examples
        console.print("\n[bold]Example commands:[/bold]")
        console.print("  • create a 3d building 40m by 40m with 4m floor height and 5 floors")
        console.print("  • make a 10-story building 50x30 meters")
        console.print("  • draw a line from origin to 100,100")
        console.print("  • create 2d floor plan 25m by 35m")
        console.print("  • draw a circle with radius 15")
        console.print("\n[bold]Other commands:[/bold] manual, save, exit")
        
        # Main loop
        while True:
            try:
                # Get input
                user_input = console.input("\n[cyan]Enter command (natural language or 'manual' for menu): [/cyan]")
                
                if user_input.lower() in ['exit', 'quit', 'q']:
                    break
                
                elif user_input.lower() == 'manual':
                    await self.manual_menu()
                
                elif user_input.lower().startswith('save'):
                    filename = user_input.replace('save', '').strip() or 'drawing'
                    result = await self.client.save_drawing(filename)
                    console.print(f"[green]Saved as {filename}.dwg[/green]")
                
                else:
                    # Process with Ollama/patterns
                    console.print("[yellow]Processing...[/yellow]")
                    command = await self.interpreter.process_with_llm(user_input)
                    
                    if command.get("action") != "unknown":
                        console.print(f"[cyan]Interpreted as: {command}[/cyan]")
                        await self.interpreter.execute_command(command)
                    else:
                        console.print("[red]Could not understand command. Try being more specific.[/red]")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
        
        await self.client.close()
        console.print("[green]Goodbye![/green]")
    
    async def manual_menu(self):
        """Manual menu mode (original interface)"""
        console.print("\n[bold]Manual Mode:[/bold]")
        console.print("1. Create 3D Building")
        console.print("2. Create 2D Building")
        console.print("3. Draw Line")
        console.print("4. Draw Circle")
        console.print("5. Back to AI mode")
        
        choice = console.input("[cyan]Select: [/cyan]")
        
        if choice == "1":
            floors = int(console.input("Floors: ") or "5")
            length = float(console.input("Length (m): ") or "30")
            width = float(console.input("Width (m): ") or "20")
            height = float(console.input("Floor height (m): ") or "3.5")
            result = await self.client.create_building_3d(floors, length, width, floor_height=height)
            console.print("[green]3D building created[/green]")
            
        elif choice == "2":
            length = float(console.input("Length (m): ") or "30")
            width = float(console.input("Width (m): ") or "20")
            result = await self.client.create_building_2d(length, width)
            console.print("[green]2D plan created[/green]")
            
        elif choice == "3":
            start_x = float(console.input("Start X: ") or "0")
            start_y = float(console.input("Start Y: ") or "0")
            end_x = float(console.input("End X: ") or "10")
            end_y = float(console.input("End Y: ") or "10")
            result = await self.client.draw_line([start_x, start_y, 0], [end_x, end_y, 0])
            console.print("[green]Line drawn[/green]")
            
        elif choice == "4":
            center_x = float(console.input("Center X: ") or "0")
            center_y = float(console.input("Center Y: ") or "0")
            radius = float(console.input("Radius: ") or "5")
            result = await self.client.draw_circle([center_x, center_y, 0], radius)
            console.print("[green]Circle drawn[/green]")

# Quick test function
async def quick_test():
    """Quick test with predefined commands"""
    interpreter = OllamaCADInterpreter()
    
    # Connect
    await interpreter.client.connect_http()
    await interpreter.client.new_drawing()
    
    # Test commands
    test_prompts = [
        "create a 3d building 40m by 40m with 4m floor height and 5 floors",
        "draw a circle with radius 20",
        "save as test_building"
    ]
    
    for prompt in test_prompts:
        console.print(f"\nTesting: {prompt}")
        command = await interpreter.process_with_llm(prompt)
        console.print(f"Parsed: {command}")
        if command.get("action") != "unknown":
            await interpreter.execute_command(command)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Run quick test
        asyncio.run(quick_test())
    else:
        # Run interactive client
        client = OllamaAutoCADClient()
        asyncio.run(client.run())
