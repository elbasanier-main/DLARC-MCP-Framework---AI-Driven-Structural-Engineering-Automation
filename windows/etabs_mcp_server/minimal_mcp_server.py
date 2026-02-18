#!/usr/bin/env python3
"""
Minimal MCP Server for Testing - Fixed Version with Better Error Handling
Save this as minimal_server.py in your structural-design-mcp folder
"""

import asyncio
import json
import sys
import logging
from typing import Any, Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add error handling for imports
try:
    from mcp.server import Server
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.error("Make sure you have mcp installed: pip install mcp")
    sys.exit(1)

class MinimalStructuralServer:
    def __init__(self):
        try:
            self.server = Server("minimal-structural-test")
            self.setup_tools()
            logger.info("✓ Minimal server initialized successfully")
        except Exception as e:
            logger.error(f"✗ Server initialization failed: {e}")
            raise

    def setup_tools(self):
        """Setup MCP tools"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            return [
                Tool(
                    name="test_connection",
                    description="Test MCP server connection",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "message": {
                                "type": "string", 
                                "description": "Test message",
                                "default": "Hello from structural MCP!"
                            }
                        }
                    }
                ),
                Tool(
                    name="simple_beam_calc",
                    description="Simple beam moment calculation",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "span": {
                                "type": "number", 
                                "description": "Beam span in meters",
                                "minimum": 0.1,
                                "maximum": 50
                            },
                            "load": {
                                "type": "number", 
                                "description": "Distributed load in kN/m",
                                "minimum": 0.1,
                                "maximum": 1000
                            }
                        },
                        "required": ["span", "load"]
                    }
                )
            ]

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            try:
                logger.info(f"Tool called: {name} with arguments: {arguments}")
                
                if name == "test_connection":
                    message = arguments.get("message", "Hello from structural MCP!")
                    response = f"✓ MCP Server connected successfully!\n\nMessage: {message}\n\nServer Status: Running\nTools Available: 2"
                    return [TextContent(type="text", text=response)]
                
                elif name == "simple_beam_calc":
                    span = arguments["span"]
                    load = arguments["load"]
                    
                    # Simple beam calculations
                    max_moment = (load * span**2) / 8  # Simply supported beam
                    max_shear = (load * span) / 2
                    max_deflection_factor = (5 * load * span**4) / (384 * 200000)  # Simplified
                    
                    result = {
                        "input": {
                            "span_m": span,
                            "load_kN_per_m": load
                        },
                        "results": {
                            "max_moment_kNm": round(max_moment, 2),
                            "max_shear_kN": round(max_shear, 2),
                            "deflection_factor": round(max_deflection_factor, 6)
                        },
                        "notes": [
                            "Simply supported beam assumed",
                            "Uniformly distributed load",
                            "Deflection factor needs section properties for actual value"
                        ]
                    }
                    
                    response = f"Beam Calculation Results:\n\n{json.dumps(result, indent=2)}"
                    return [TextContent(type="text", text=response)]
                
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]
                    
            except Exception as e:
                error_msg = f"Error in tool '{name}': {str(e)}"
                logger.error(error_msg)
                return [TextContent(type="text", text=error_msg)]

async def main():
    """Main server entry point"""
    try:
        logger.info("Starting minimal structural MCP server...")
        server_instance = MinimalStructuralServer()
        
        # Add timeout and better error handling
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Server running and waiting for connections...")
            
            try:
                await server_instance.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="minimal-structural-test",
                        server_version="1.0.0",
                        capabilities=server_instance.server.get_capabilities(
                            notification_options=None,
                            experimental_capabilities=None
                        )
                    ),
                )
            except asyncio.CancelledError:
                logger.info("Server cancelled")
                raise
            except Exception as e:
                logger.error(f"Error during server run: {e}")
                raise
                
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)