# DLARC MCP Framework - AI-Driven Structural Engineering Automation

## Research Context

This package is a **first pre-step** of the research program at **DLARC (Deep Learning Architecture Research Center)** focused on AI-driven structural engineering automation.

The framework demonstrates how LLM-based AI agents can orchestrate complex engineering software workflows through **conversational natural language** using the **Model Context Protocol (MCP)**. Rather than requiring engineers to manually operate CAD and analysis software through traditional GUIs, this system enables natural language commands like *"Create a 10-floor shear wall building and export it for structural analysis"* to be executed automatically across multiple software platforms.

This represents a foundational step toward **ASTRA (Autonomous Structural Transformation & Rational Analysis System)** - a comprehensive AI structural engineering assistant.

## Architecture

```
+-------------------+     SSH/MCP      +-------------------+
|     Ubuntu         | <-------------> |     Windows        |
|  Ollama + CodeLlama|                 |  AutoCAD 2024      |
|  LLM inference     |                 |  ETABS v21         |
|  Ollama clients    |                 |  MCP Servers        |
+-------------------+                 |  pywin32 COM        |
                                       +-------------------+
+-------------------+     SSH/MCP              ^
|     macOS          | <-----------------------+
|  Claude Desktop    |
|  MCP clients       |
+-------------------+
```

### Platform Roles

| Platform | Role | Key Software |
|----------|------|-------------|
| **Windows** | Engineering software host | AutoCAD 2024, ETABS v21, MCP servers, pywin32 COM automation |
| **Ubuntu** | LLM inference host | Ollama, CodeLlama (7B/13B/34B), Ollama MCP clients |
| **macOS** | User interface | Claude Desktop, Claude Desktop MCP clients |

## PLACEHOLDER DATA NOTICE

The following 6 JSON files contain **placeholder/example data** that users must replace with their own standards data:

| File | Location | Replace With |
|------|----------|-------------|
| `acixx2_concrete.json` | standards_module/data/materials/ | Your concrete design code (e.g., ACI 318-19) |
| `acixx_formwork.json` | standards_module/data/construction/ | Your formwork design code (e.g., ACI 347-04) |
| `asce_placeholder_combinations.json` | standards_module/data/loads/ | Your load combination code (e.g., ASCE 7-22) |
| `productivity_standards.json` | standards_module/data/construction/ | Regional productivity rates |
| `ifc4_placeholder_mappings.json` | standards_module/data/codes/ | IFC4 mappings (customizable) |
| `construction_sequences.json` | standards_module/data/codes/ | Construction sequences (customizable) |

## Package Structure

```
dlarc-mcp-framework/
+-- README.md
+-- example_claude_chat_session.md
+-- windows/
|   +-- autocad_mcp_server/
|   |   +-- autocad_2024_mcp_server.py      # Main MCP server (2832 lines)
|   |   +-- house.py                         # House generator (all 14 params)
|   |   +-- autocad_etabs_convert.py         # AutoCAD-ETABS converter
|   |   +-- dxf_to_dataframe.py              # DXF file parser
|   |   +-- construction_validation.py       # Standards-based validation
|   |   +-- shear_wall/
|   |   |   +-- building_dataframe.py        # Parametric shear wall generator
|   |   |   +-- building_dataframe_simple.py # Predefined reference building
|   |   |   +-- __init__.py
|   |   +-- visualization_report_module/
|   |   |   +-- visualization_report_module.py  # Report generator
|   |   |   +-- modern_gantt_with_metrics.py    # Gantt chart
|   |   |   +-- __init__.py
|   |   +-- standards_module/
|   |   |   +-- standards_manager.py         # Standards query interface
|   |   |   +-- __init__.py
|   |   |   +-- data/                        # 6 placeholder JSON files
|   |   +-- construction_ai_modules/
|   |       +-- construction_sequencing.py   # AI construction sequencer
|   |       +-- etabs_autocad_pattern_learner.py
|   |       +-- __init__.py
|   +-- etabs_mcp_server/
|   |   +-- enhanced_etabs_server.py         # Main ETABS server (5 tools)
|   |   +-- corrected_etabs_excel_server.py  # Corrected table format
|   |   +-- fixed_etabs21_server.py          # Syntax-fixed version
|   |   +-- simple_etabs_server.py           # Minimal test version
|   |   +-- minimal_mcp_server.py            # Debug server
|   |   +-- fixed_mcp_integration.py         # Ollama + ETABS integration
|   |   +-- README.md
|   |   +-- __init__.py
|   +-- config/
|   |   +-- claude_desktop_config.json
|   +-- requirements_windows.txt
+-- ubuntu/
|   +-- autocad_ollama_client.py             # Ollama + AutoCAD MCP
|   +-- autocad_ubuntu_client.py             # Ubuntu AutoCAD client
|   +-- etabs_ollama_client.py               # Ollama + ETABS MCP
|   +-- unified_ollama_client.py             # Unified client (both servers)
|   +-- client_integration_ui.py             # UI integration module
|   +-- ubuntu_install_fix.py                # Dependency fix script
|   +-- requirements_ubuntu.txt
|   +-- ollama_installation_instructions.md
+-- macos/
    +-- autocad_mcp_client.py                # Claude Desktop AutoCAD client
    +-- etabs_mcp_client.py                  # Claude Desktop ETABS client
    +-- claude_desktop_config.json           # SSH bridge config
    +-- requirements_macos.txt
```

## Quick Start

### Windows (MCP Servers)

```bash
cd windows/autocad_mcp_server
pip install -r ../requirements_windows.txt

# Start AutoCAD MCP server
python autocad_2024_mcp_server.py

# In another terminal, start ETABS MCP server
cd ../etabs_mcp_server
python enhanced_etabs_server.py
```

### Ubuntu (Ollama Clients)

```bash
# Install Ollama (see ollama_installation_instructions.md)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull codellama:34b

# Install dependencies
cd ubuntu
pip install -r requirements_ubuntu.txt

# Run unified client
python unified_ollama_client.py
```

### macOS (Claude Desktop)

```bash
# Copy config (update WINDOWS_IP and USERNAME first)
cp macos/claude_desktop_config.json ~/Library/Application\ Support/Claude/

# Restart Claude Desktop - servers will be available automatically
```

## AutoCAD MCP Server Tools

| Tool | Description |
|------|-------------|
| `connect_autocad` | Connect to AutoCAD 2024 via COM |
| `new_drawing` | Create new drawing |
| `draw_line` / `draw_circle` | Basic geometry |
| `create_building_2d` | 2D floor plan |
| `create_3d_building` | 3D building model |
| `create_house` | Complete house (14 parameters: floors, style, rooms, garage, pool, MEP, etc.) |
| `create_shear_wall_building` | Parametric or predefined shear wall building |
| `save_drawing` / `save_as_dxf` | Save in DWG or DXF format |
| `zoom_extents` | Zoom to fit all objects |
| `extract_building_data` | Extract geometry from current model |
| `generate_comprehensive_construction_report` | Full construction report with Gantt chart |
| `query_standard` | Query building standards (ASCE, ACI, AISC, IFC4) |
| `get_load_combinations` | LRFD/ASD load combinations |
| `validate_for_export` | Check model ready for ETABS/IFC export |
| `query_aci_318_complete` | Concrete design queries |
| `query_formwork` | Formwork design queries |
| `query_productivity` | Construction productivity rates |

## Enhanced ETABS MCP Server Tools

| Tool | Description |
|------|-------------|
| `test_connection` | Verify ETABS COM connection |
| `design_building` | Complete structural model (grid, materials, sections, stories, loads) |
| `export_etabs21_excel` | Generate .xlsx files for ETABS 21 import |
| `list_exported_files` | List generated Excel files |
| `generate_import_instructions` | Step-by-step ETABS import guide |

## References

- Model Context Protocol (MCP): https://modelcontextprotocol.io
- DLARC Research: Deep Learning Architecture Research Center
- Target journal: Automation in Construction
