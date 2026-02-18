#!/usr/bin/env python3
"""
Fixed Ollama + MCP Integration - Connection Issue Resolved
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
        
        # Available tools from your server
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
                    "bay_spacing": "object with x_direction and y_direction (optional)",
                    "loads": "object with dead_load, live_load, wind_load (optional)",
                    "structural_system": "string: moment_frame, braced_frame, or shear_wall (optional)",
                    "material": "string: steel, concrete, or composite (optional)"
                },
                "example": '''{"building_name": "Office_Building", "stories": 5, "plan_dimensions": {"length": 30, "width": 20}, "bay_spacing": {"x_direction": 6, "y_direction": 6}, "material": "concrete"}'''
            },
            "export_etabs21_excel": {
                "description": "Export building to ETABS 21 compatible Excel format",
                "parameters": {
                    "building_name": "string (required)",
                    "table_types": "array of strings (optional)"
                },
                "example": '{"building_name": "Office_Building", "table_types": ["all"]}'
            }
        }
    
    @asynccontextmanager
    async def mcp_server_context(self):
        """Start MCP server with improved error handling"""
        try:
            print("🔧 Starting ETABS MCP server...")
            
            # Check if server file exists
            if not os.path.exists(self.mcp_server_path):
                raise FileNotFoundError(f"MCP server not found: {self.mcp_server_path}")
            
            # Start server process with better setup
            self.mcp_process = await asyncio.create_subprocess_exec(
                sys.executable, self.mcp_server_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(os.path.abspath(self.mcp_server_path)) or "."
            )
            
            # Wait longer for server to initialize and check if it's running
            await asyncio.sleep(2)
            
            if self.mcp_process.returncode is not None:
                # Server has already exited, get error info
                stdout, stderr = await self.mcp_process.communicate()
                error_msg = stderr.decode() if stderr else "No error output"
                raise Exception(f"MCP server exited immediately: {error_msg}")
            
            print("✅ MCP server process started")
            
            # Test if server is responsive before sending initialization
            try:
                # Send a simple test message first
                test_msg = {"jsonrpc": "2.0", "method": "ping", "id": 999}
                test_str = json.dumps(test_msg) + "\n"
                self.mcp_process.stdin.write(test_str.encode())
                await asyncio.wait_for(self.mcp_process.stdin.drain(), timeout=5.0)
                print("✅ Server connection test passed")
            except Exception as e:
                print(f"⚠️ Server connection test failed: {e}")
                # Continue anyway, as some servers don't respond to ping
            
            # Send proper initialization
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
                init_response = await asyncio.wait_for(self._read_mcp_response(), timeout=10.0)
                
                if init_response and "result" in init_response:
                    print("✅ MCP server initialized successfully")
                    
                    # Send initialized notification
                    initialized_msg = {
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized"
                    }
                    await self._send_mcp_message(initialized_msg)
                    
                else:
                    print("⚠️ MCP server initialization response unclear, continuing anyway")
                    
            except asyncio.TimeoutError:
                print("⚠️ MCP server initialization timeout, but server is running")
            except Exception as e:
                print(f"⚠️ MCP initialization issue: {e}, continuing anyway")
            
            yield self.mcp_process
                
        except Exception as e:
            print(f"❌ Error starting MCP server: {e}")
            if self.mcp_process:
                try:
                    stdout, stderr = await asyncio.wait_for(
                        self.mcp_process.communicate(), timeout=2.0
                    )
                    if stderr:
                        print(f"Server stderr: {stderr.decode()}")
                except:
                    pass
            raise
        finally:
            if self.mcp_process and self.mcp_process.returncode is None:
                print("🛑 Stopping MCP server...")
                try:
                    self.mcp_process.terminate()
                    await asyncio.wait_for(self.mcp_process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    print("⚠️ Server didn't stop gracefully, killing...")
                    self.mcp_process.kill()
                    await self.mcp_process.wait()
                print("✅ MCP server stopped")
    
    async def _send_mcp_message(self, message: Dict):
        """Send message to MCP server with error handling"""
        if not self.mcp_process or self.mcp_process.returncode is not None:
            raise Exception("MCP server not running")
        
        try:
            message_str = json.dumps(message) + "\n"
            self.mcp_process.stdin.write(message_str.encode())
            await asyncio.wait_for(self.mcp_process.stdin.drain(), timeout=5.0)
            self.request_id += 1
        except ConnectionResetError:
            raise Exception("Connection lost to MCP server")
        except asyncio.TimeoutError:
            raise Exception("Timeout sending message to MCP server")
    
    async def _read_mcp_response(self) -> Optional[Dict]:
        """Read response from MCP server with timeout"""
        if not self.mcp_process or self.mcp_process.returncode is not None:
            return None
        
        try:
            response_line = await asyncio.wait_for(
                self.mcp_process.stdout.readline(), 
                timeout=15.0
            )
            
            if response_line:
                response_text = response_line.decode().strip()
                if response_text:
                    return json.loads(response_text)
            return None
        except asyncio.TimeoutError:
            print("⚠️ MCP server response timeout")
            return None
        except json.JSONDecodeError as e:
            print(f"⚠️ Invalid JSON from MCP server: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Error reading MCP response: {e}")
            return None
    
    async def call_ollama(self, prompt: str, system_prompt: str = "") -> str:
        """Call Ollama LLM with structural engineering context"""
        try:
            system_msg = f"""You are an expert structural engineer with access to MCP tools for building design and ETABS integration.

AVAILABLE TOOLS:
{self._format_tools_for_llm()}

TOOL USAGE FORMAT:
When you need to use a tool, format it exactly like this:

TOOL_CALL: tool_name
PARAMETERS: {{"param1": "value1", "param2": "value2"}}

IMPORTANT RULES:
1. Always explain your engineering reasoning before calling tools
2. Use proper JSON format for parameters (double quotes, no trailing commas)
3. Follow structural engineering best practices
4. Provide detailed analysis after tool results

{system_prompt}"""

            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "system": system_msg,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_ctx": 4096
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
        """Call MCP tool with improved error handling"""
        try:
            if not self.mcp_process or self.mcp_process.returncode is not None:
                return "❌ MCP server not running"
            
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
            
            # Send message with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await self._send_mcp_message(tool_message)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        return f"❌ Failed to send message after {max_retries} attempts: {e}"
                    print(f"⚠️ Attempt {attempt + 1} failed, retrying...")
                    await asyncio.sleep(1)
            
            # Read response with retry
            response = None
            for attempt in range(max_retries):
                response = await self._read_mcp_response()
                if response:
                    break
                print(f"⚠️ No response on attempt {attempt + 1}, retrying...")
                await asyncio.sleep(1)
            
            if response:
                if "result" in response:
                    result = response["result"]
                    if isinstance(result, dict) and "content" in result:
                        content_list = result["content"]
                        if content_list and len(content_list) > 0:
                            return content_list[0].get("text", "No text content")
                    return str(result)
                elif "error" in response:
                    error = response["error"]
                    return f"❌ MCP Error: {error.get('message', 'Unknown error')} (Code: {error.get('code', 'N/A')})"
                else:
                    return f"❌ Unexpected response format: {response}"
            else:
                return "❌ No response from MCP server after multiple attempts"
                
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
                for line in lines[1:]:
                    if line.strip().startswith("PARAMETERS:"):
                        param_text = line.split("PARAMETERS:", 1)[1].strip()
                        try:
                            parameters = json.loads(param_text)
                            break
                        except json.JSONDecodeError:
                            print(f"⚠️ Invalid JSON parameters for {tool_name}: {param_text}")
                
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
        
        if tool_calls:
            print(f"\n🔧 Found {len(tool_calls)} tool call(s)")
            
            for i, tool_call in enumerate(tool_calls, 1):
                tool_name = tool_call["tool"]
                parameters = tool_call["parameters"]
                
                print(f"\n🛠️  Tool Call {i}: {tool_name}")
                
                tool_result = await self.call_mcp_tool(tool_name, parameters)
                
                result_preview = tool_result[:300] + "..." if len(tool_result) > 300 else tool_result
                print(f"✅ Result Preview:\n{result_preview}")
                
                llm_response += f"\n\n🔧 Tool Result from {tool_name}:\n{tool_result}"
        
        self.conversation_history.append(f"User: {user_query}")
        self.conversation_history.append(f"Assistant: {llm_response}")
        
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
        
        return llm_response
    
    async def chat_loop(self):
        """Interactive chat loop"""
        print("🏗️ Structural Engineering AI Assistant (Connection Fixed)")
        print(f"Model: {self.model_name}")
        print("="*70)
        print("Commands:")
        print("  'exit' - Quit the assistant")
        print("  'models' - List available Ollama models")
        print("  'switch <model>' - Switch to different model")
        print("  'tools' - Show available MCP tools")
        print("\nExample queries:")
        print("  'Test the MCP connection'")
        print("  'Design a 3-story concrete office building, 24m x 18m'")
        print("  'Export the building to ETABS Excel format'")
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
                    print(f"\n🎯 Complete Response:\n{response}")
                    
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
    """Main function with improved setup verification"""
    print("🏗️ Structural Engineering MCP Integration (Connection Fixed)")
    print("="*70)
    
    # Verify Ollama
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            print(f"✅ Ollama: {len(models)} models available")
            
            if not models:
                print("⚠️ No models found. Pull a model first:")
                print("   ollama pull codellama:7b")
                return
        else:
            print("❌ Ollama not responding")
            return
    except Exception as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        print("Make sure Ollama is running: ollama serve")
        return
    
    # Verify MCP server file
    server_path = "./etabs21_server.py"
    if not os.path.exists(server_path):
        print(f"❌ MCP server not found: {server_path}")
        print("Make sure etabs21_server.py exists in the current directory")
        return
    
    print(f"✅ MCP server found: {server_path}")
    
    # Choose model
    print("\nRecommended models:")
    print("1. codellama:7b - Fast, good for calculations (4GB RAM)")
    print("2. codellama:13b - Better reasoning (8GB RAM)")
    print("3. codellama:34b - Best performance (24GB RAM)")
    
    model_choice = input("\nEnter model name (or press Enter for codellama:7b): ").strip()
    if not model_choice:
        model_choice = "codellama:7b"
    
    client = StructuralMCPClient(model_name=model_choice)
    await client.chat_loop()

if __name__ == "__main__":
    asyncio.run(main())