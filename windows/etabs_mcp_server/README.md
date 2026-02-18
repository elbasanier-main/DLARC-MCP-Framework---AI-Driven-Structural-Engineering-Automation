# ETABS MCP Server Package

## Server Versions

| File | Description | Tools |
|------|-------------|-------|
| `enhanced_etabs_server.py` | **Main server** - Full ETABS 21 with Excel file generation | test_connection, design_building, export_etabs21_excel, list_exported_files, generate_import_instructions |
| `corrected_etabs_excel_server.py` | Corrected ETABS database table format for proper import | Same 5 tools with corrected table format |
| `fixed_etabs21_server.py` | Syntax-corrected version (no emoji in code) | Same 5 tools |
| `simple_etabs_server.py` | Minimal working version for testing | test_connection, design_building |
| `minimal_mcp_server.py` | Bare minimum MCP server for debugging | test_connection only |
| `fixed_mcp_integration.py` | Ollama + MCP integration client for ETABS | Client-side integration |

## Recommended Usage

- **Production**: Use `enhanced_etabs_server.py` (most complete, generates .xlsx files)
- **Debugging**: Start with `minimal_mcp_server.py`, then `simple_etabs_server.py`
- **Ubuntu/Ollama**: Use `fixed_mcp_integration.py` as the client

## Enhanced ETABS Server Tools (5 tools)

1. **test_connection** - Verify ETABS COM connection
2. **design_building** - Create complete structural model (grid, materials, sections, stories, frames, loads)
3. **export_etabs21_excel** - Generate actual .xlsx files formatted for ETABS 21 import
4. **list_exported_files** - List all generated Excel files in export directory
5. **generate_import_instructions** - Step-by-step ETABS import guide for generated files

## Setup

```bash
pip install mcp openpyxl pywin32
python enhanced_etabs_server.py
```
