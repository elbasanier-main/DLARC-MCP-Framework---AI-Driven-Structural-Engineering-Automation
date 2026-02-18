#!/usr/bin/env python3
"""
Fixed Ollama + MCP Integration - Properly handles enhanced ETABS server
"""

import asyncio
import json
import subprocess
import sys
import re
import os
import time
from typing import Dict, List, Any, Optional
import requests
from contextlib import asynccontextmanager

class StructuralMCPClient:
    def __init__(self, 
                 model_name="codellama:7b",
                 mcp_server_path="./etabs21_server.py",
                 ollama_host="http://localhost:11434"):
        
        self.model_name = model_name
        self.mcp_server_path = mcp_server_path
        self.ollama_host = ollama_host
        self.mcp_process = None
        self.conversation_history = []
        self.request_id = 1
        
        # Updated tool definitions for enhanced server
        self.available_tools = {
            "test_connection": {
                "description": "Test MCP server connection",
                "parameters": {
                    "message": "string (optional)"
                },
                "example": '{"message": "Hello from Ollama!"}'
            },
            "design_building": {
                "description": "Design a complete building structure for ETABS 21",
                "parameters": {
                    "building_name": "string (required)",
                    "stories": "integer (required)", 
                    "plan_dimensions": "object with length and width (required)",
                    "story_height": "number (optional, default: 3.5)",
                    "bay_spacing": "object with x_direction and y_direction (optional)",
                    "loads": "object with dead_load, live_load, wind_load (optional)",
                    "structural_system": "string: moment_frame, braced_frame, or shear_wall (optional)",
                    "material": "string: steel, concrete, or composite (optional)"
                },
                "example": '''{"building_name": "Office_Building", "stories": 5, "plan_dimensions": {"length": 30, "width": 20}, "bay_spacing": {"x_direction": 6, "y_direction": 6}, "material": "concrete"}'''
            },
            "export_etabs21_excel": {
                "description": "Export to ETABS 21 compatible Excel file (.xlsx)",
                "parameters": {
                    "building_name": "string (required)",
                    "save_file": "boolean (optional, default: true)",
                    "file_path": "string (optional)",
                    "table_types": "array of strings (optional, default: ['all'])"
                },
                "example": '{"building_name": "Office_Building"}'
            },
            "list_exported_files": {
                "description": "List all exported ETABS files",
                "parameters": {
                    "file_type": "string: xlsx or all (optional, default: all)"
                },
                "example": '{"file_type": "xlsx"}'
            },
            "generate_import_instructions": {
                "description": "Generate detailed ETABS import instructions",
                "parameters": {
                    "file_name": "string (required)"
                },
                "example": '{"file_name": "Office_Building_ETABS_20240804_123456.xlsx"}'
            }
        }
    
    @asynccontextmanager
    async def mcp_server_context(self):
        """Start MCP server with improved error handling"""
        try:
            print("🔧 Starting Enhanced ETABS MCP server...")
            
            # Check if server file exists
            if not os.path.exists(self.mcp_server_path):
                raise FileNotFoundError(f"MCP server not found: {self.mcp_server_path}")
            
            # Start server process
            self.mcp_process = await asyncio.create_subprocess_exec(
                sys.executable, self.mcp_server_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(os.path.abspath(self.mcp_server_path)) or "."
            )
            
            # Wait for server to initialize
            await asyncio.sleep(2)
            
            if self.mcp_process.returncode is not None:
                stdout, stderr = await self.mcp_process.communicate()
                error_msg = stderr.decode() if stderr else "No error output"
                raise Exception(f"MCP server exited immediately: {error_msg}")
            
            print("✅ MCP server process started")
            
            # Send initialization
            init_message = {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "structural-ollama-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            try:
                await self._send_mcp_message(init_message)
                # Wait for initialization response
                await asyncio.sleep(1)
                # Clear any initialization messages
                await self._clear_mcp_buffer()
                print("✅ MCP server initialized")
                    
            except Exception as e:
                print(f"⚠️ MCP initialization issue: {e}, continuing anyway")
            
            yield self.mcp_process
                
        except Exception as e:
            print(f"❌ Error starting MCP server: {e}")
            raise
        finally:
            if self.mcp_process and self.mcp_process.returncode is None:
                print("🛑 Stopping MCP server...")
                try:
                    self.mcp_process.terminate()
                    await asyncio.wait_for(self.mcp_process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self.mcp_process.kill()
                    await self.mcp_process.wait()
                print("✅ MCP server stopped")
    
    async def _clear_mcp_buffer(self):
        """Clear any pending messages from MCP server"""
        try:
            while True:
                line = await asyncio.wait_for(self.mcp_process.stdout.readline(), timeout=0.1)
                if not line:
                    break
        except asyncio.TimeoutError:
            pass
    
    async def _send_mcp_message(self, message: Dict):
        """Send message to MCP server"""
        if not self.mcp_process or self.mcp_process.returncode is not None:
            raise Exception("MCP server not running")
        
        message_str = json.dumps(message) + "\n"
        self.mcp_process.stdin.write(message_str.encode())
        await self.mcp_process.stdin.drain()
        self.request_id += 1
    
    async def _read_mcp_response(self) -> Optional[Dict]:
        """Read response from MCP server"""
        if not self.mcp_process or self.mcp_process.returncode is not None:
            return None
        
        try:
            response_line = await asyncio.wait_for(
                self.mcp_process.stdout.readline(), 
                timeout=30.0  # Increased timeout for complex operations
            )
            
            if response_line:
                response_text = response_line.decode().strip()
                if response_text:
                    try:
                        return json.loads(response_text)
                    except json.JSONDecodeError:
                        # Sometimes responses are split across lines
                        return {"result": [{"type": "text", "text": response_text}]}
            return None
        except asyncio.TimeoutError:
            print("⚠️ MCP server response timeout")
            return None
    
    async def call_ollama(self, prompt: str, system_prompt: str = "") -> str:
        """Call Ollama LLM with structural engineering context"""
        try:
            system_msg = f"""You are an expert structural engineer with access to MCP tools for building design and ETABS integration.

AVAILABLE TOOLS:
{self._format_tools_for_llm()}

CRITICAL INSTRUCTIONS FOR TOOL USAGE:
1. When you need to use a tool, format it EXACTLY like this:
   TOOL_CALL: tool_name
   PARAMETERS: {{"param1": "value1", "param2": "value2"}}

2. For building design requests, ALWAYS use the design_building tool
3. For export requests, use export_etabs21_excel with just the building_name
4. Always explain your engineering reasoning
5. Use proper JSON format for parameters (double quotes, no trailing commas)

EXAMPLE TOOL CALLS:
- Design request:
  TOOL_CALL: design_building
  PARAMETERS: {{"building_name": "Office_Building", "stories": 5, "plan_dimensions": {{"length": 30, "width": 20}}, "material": "concrete"}}

- Export request:
  TOOL_CALL: export_etabs21_excel
  PARAMETERS: {{"building_name": "Office_Building"}}

{system_prompt}"""

            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "system": system_msg,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_ctx": 4096,
                    "seed": 42
                }
            }
            
            response = requests.post(
                f"{self.ollama_host}/api/generate",
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "No response from Ollama")
            else:
                return f"Ollama error: HTTP {response.status_code}"
                
        except Exception as e:
            return f"Error calling Ollama: {str(e)}"
    
    def _format_tools_for_llm(self) -> str:
        """Format available tools for LLM context"""
        formatted = []
        for tool_name, tool_info in self.available_tools.items():
            formatted.append(f"""
- {tool_name}:
  Description: {tool_info['description']}
  Parameters: {tool_info['parameters']}
  Example: {tool_info['example']}""")
        return "\n".join(formatted)
    
    async def call_mcp_tool(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """Call MCP tool with proper response handling"""
        try:
            if not self.mcp_process or self.mcp_process.returncode is not None:
                return "❌ MCP server not running"
            
            # Clear any pending messages
            await self._clear_mcp_buffer()
            
            # Format proper MCP tool call message
            tool_message = {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": parameters
                }
            }
            
            print(f"🔧 Calling MCP tool: {tool_name}")
            print(f"📋 Parameters: {json.dumps(parameters, indent=2)}")
            
            # Send message
            await self._send_mcp_message(tool_message)
            
            # Read all responses until we get the actual result
            result_text = ""
            attempts = 0
            max_attempts = 10
            
            while attempts < max_attempts:
                response = await self._read_mcp_response()
                if response:
                    if "result" in response:
                        # Extract text content from result
                        result = response["result"]
                        if isinstance(result, list):
                            for item in result:
                                if isinstance(item, dict) and "text" in item:
                                    result_text = item["text"]
                                    break
                        elif isinstance(result, dict) and "content" in result:
                            content_list = result["content"]
                            if isinstance(content_list, list) and len(content_list) > 0:
                                result_text = content_list[0].get("text", "")
                        elif isinstance(result, str):
                            result_text = result
                        
                        if result_text:
                            return result_text
                    elif "error" in response:
                        error = response["error"]
                        return f"❌ MCP Error: {error.get('message', 'Unknown error')} (Code: {error.get('code', 'N/A')})"
                
                attempts += 1
                await asyncio.sleep(0.5)
            
            return "❌ No valid response from MCP server after multiple attempts"
                
        except Exception as e:
            return f"❌ Error calling MCP tool: {str(e)}"
    
    def parse_tool_calls(self, llm_response: str) -> List[Dict]:
        """Parse tool calls from LLM response"""
        tool_calls = []
        
        sections = llm_response.split("TOOL_CALL:")
        
        for section in sections[1:]:
            lines = section.strip().split("\n")
            
            if lines:
                tool_name = lines[0].strip()
                
                parameters = {}
                for i, line in enumerate(lines[1:]):
                    if line.strip().startswith("PARAMETERS:"):
                        # Get everything after PARAMETERS: including multi-line JSON
                        param_start = lines[i+1:].index(line) + 1
                        param_text = "\n".join(lines[param_start:])
                        param_text = param_text.split("PARAMETERS:", 1)[1].strip()
                        
                        # Find the JSON object
                        json_match = re.search(r'\{.*\}', param_text, re.DOTALL)
                        if json_match:
                            try:
                                parameters = json.loads(json_match.group())
                                break
                            except json.JSONDecodeError:
                                print(f"⚠️ Invalid JSON parameters for {tool_name}")
                
                if tool_name and parameters:
                    tool_calls.append({
                        "tool": tool_name,
                        "parameters": parameters
                    })
        
        return tool_calls
    
    async def process_query(self, user_query: str) -> str:
        """Process user query with LLM and execute tools"""
        print(f"\n👤 User: {user_query}")
        print("🤖 LLM: Analyzing query...")
        
        context = ""
        if self.conversation_history:
            recent_history = self.conversation_history[-4:]
            context = "Recent conversation:\n" + "\n".join(recent_history) + "\n\n"
        
        full_prompt = f"{context}Current query: {user_query}"
        llm_response = await self.call_ollama(full_prompt)
        
        print(f"\n🧠 LLM Response:\n{llm_response}")
        
        tool_calls = self.parse_tool_calls(llm_response)
        
        tool_results = []
        if tool_calls:
            print(f"\n🔧 Found {len(tool_calls)} tool call(s)")
            
            for i, tool_call in enumerate(tool_calls, 1):
                tool_name = tool_call["tool"]
                parameters = tool_call["parameters"]
                
                print(f"\n🛠️  Tool Call {i}: {tool_name}")
                
                tool_result = await self.call_mcp_tool(tool_name, parameters)
                tool_results.append((tool_name, tool_result))
                
                print(f"✅ Result:\n{tool_result}")
        
        # Build final response
        final_response = llm_response
        
        if tool_results:
            final_response += "\n\n📊 RESULTS:\n"
            for tool_name, result in tool_results:
                final_response += f"\n🔧 {tool_name}:\n{result}\n"
        
        self.conversation_history.append(f"User: {user_query}")
        self.conversation_history.append(f"Assistant: {final_response}")
        
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        
        return final_response
    
    async def chat_loop(self):
        """Interactive chat loop"""
        print("🏗️ Structural Engineering AI Assistant (Enhanced ETABS Integration)")
        print(f"Model: {self.model_name}")
        print("="*70)
        print("Commands:")
        print("  'exit' - Quit the assistant")
        print("  'models' - List available Ollama models")
        print("  'switch <model>' - Switch to different model")
        print("  'tools' - Show available MCP tools")
        print("\nExample queries:")
        print("  'Test the MCP connection'")
        print("  'Design a 5-story concrete office building, 30m x 20m'")
        print("  'Export the building to ETABS Excel format'")
        print("  'List all exported files'")
        print("="*70)
        
        async with self.mcp_server_context():
            while True:
                try:
                    user_input = input("\n🏗️ Engineer: ").strip()
                    
                    if user_input.lower() == 'exit':
                        break
                    elif user_input.lower() == 'models':
                        self.list_available_models()
                        continue
                    elif user_input.lower().startswith('switch '):
                        new_model = user_input.split(' ', 1)[1]
                        self.model_name = new_model
                        print(f"Switched to model: {new_model}")
                        continue
                    elif user_input.lower() == 'tools':
                        self.show_available_tools()
                        continue
                    elif not user_input:
                        continue
                    
                    response = await self.process_query(user_input)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")
        
        print("\n👋 Goodbye!")
    
    def list_available_models(self):
        """List available Ollama models"""
        try:
            response = requests.get(f"{self.ollama_host}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                print("\n📚 Available Models:")
                for model in models:
                    name = model.get("name", "Unknown")
                    size = model.get("size", 0) / (1024**3)
                    print(f"  • {name} ({size:.1f} GB)")
            else:
                print("❌ Could not fetch models from Ollama")
        except Exception as e:
            print(f"❌ Error fetching models: {e}")
    
    def show_available_tools(self):
        """Show available MCP tools"""
        print("\n🛠️  Available MCP Tools:")
        for tool_name, tool_info in self.available_tools.items():
            print(f"\n• {tool_name}:")
            print(f"  Description: {tool_info['description']}")
            print(f"  Example: {tool_info['example']}")

async def main():
    """Main function"""
    print("🏗️ Structural Engineering MCP Integration (Enhanced ETABS Support)")
    print("="*70)
    
    # Verify Ollama
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"✅ Ollama: {len(models)} models available")
        else:
            print("❌ Ollama not responding")
            return
    except Exception as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        return
    
    # Verify MCP server file
    server_path = "./etabs21_server.py"
    if not os.path.exists(server_path):
        print(f"❌ MCP server not found: {server_path}")
        return
    
    print(f"✅ MCP server found: {server_path}")
    
    # Choose model
    model_choice = input("\nEnter model name (or press Enter for codellama:34b): ").strip()
    if not model_choice:
        model_choice = "codellama:34b"
    
    client = StructuralMCPClient(model_name=model_choice)
    await client.chat_loop()

if __name__ == "__main__":
    asyncio.run(main())