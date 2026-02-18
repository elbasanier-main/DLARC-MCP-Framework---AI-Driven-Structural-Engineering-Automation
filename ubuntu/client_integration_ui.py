#!/usr/bin/env python3
"""
Client Integration Module for AutoCAD-ETABS Bridge
Provides user-friendly interface and workflow automation
"""

import asyncio
import json
import os
import sys
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import MCP client libraries
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    logger.warning("MCP client libraries not available")

# ==================== Configuration ====================

class BridgeConfig:
    """Configuration for AutoCAD-ETABS Bridge"""
    
    DEFAULT_CONFIG = {
        "server": {
            "command": "python",
            "args": ["autocad_etabs_bridge_server.py"],
            "cwd": os.getcwd()
        },
        "autocad": {
            "default_units": "meters",
            "layer_mapping": {
                "S-COLS": "columns",
                "S-BEAM": "beams",
                "S-SLAB": "slabs",
                "S-WALL": "walls",
                "S-FNDN": "foundations"
            }
        },
        "etabs": {
            "default_material": "CONCRETE",
            "default_section": "AUTO",
            "output_directory": "etabs_output",
            "excel_version": "2021"
        },
        "processing": {
            "tolerance": 0.001,
            "merge_distance": 0.01,
            "tessellation_resolution": 0.1
        }
    }
    
    def __init__(self, config_file: str = "bridge_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return self.DEFAULT_CONFIG.copy()
    
    def save_config(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key_path: str, default=None):
        """Get configuration value by dot-separated path"""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value
    
    def set(self, key_path: str, value):
        """Set configuration value by dot-separated path"""
        keys = key_path.split('.')
        target = self.config
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
        target[keys[-1]] = value

# ==================== MCP Client ====================

class BridgeMCPClient:
    """MCP client for AutoCAD-ETABS Bridge"""
    
    def __init__(self, config: BridgeConfig):
        self.config = config
        self.session = None
        self.connected = False
    
    async def connect(self) -> bool:
        """Connect to MCP server"""
        try:
            server_params = StdioServerParameters(
                command=self.config.get("server.command", "python"),
                args=self.config.get("server.args", ["autocad_etabs_bridge_server.py"]),
                cwd=self.config.get("server.cwd", os.getcwd())
            )
            
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    self.session = session
                    await session.initialize()
                    
                    # List available tools
                    tools = await session.list_tools()
                    logger.info(f"Connected to server with {len(tools)} tools available")
                    
                    self.connected = True
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            return False
    
    async def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """Call MCP tool"""
        if not self.connected or not self.session:
            raise RuntimeError("Not connected to MCP server")
        
        try:
            result = await self.session.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from MCP server"""
        if self.session:
            # Session cleanup handled by context manager
            self.session = None
            self.connected = False

# ==================== Workflow Manager ====================

class WorkflowManager:
    """Manages conversion workflow"""
    
    def __init__(self, config: BridgeConfig):
        self.config = config
        self.client = BridgeMCPClient(config)
        self.current_project = None
        self.conversion_history = []
    
    async def execute_workflow(
        self,
        input_file: str,
        output_format: str = "etabs",
        options: Dict = None
    ) -> Dict:
        """Execute complete conversion workflow"""
        
        workflow_result = {
            "status": "started",
            "input_file": input_file,
            "output_format": output_format,
            "steps": [],
            "errors": [],
            "warnings": []
        }
        
        try:
            # Connect to server
            if not self.client.connected:
                await self.client.connect()
            
            # Step 1: Import AutoCAD file
            logger.info(f"Importing AutoCAD file: {input_file}")
            import_result = await self.client.call_tool(
                "import_autocad",
                {"filepath": input_file}
            )
            workflow_result["steps"].append({
                "name": "import",
                "status": "success",
                "result": import_result
            })
            
            # Step 2: Analyze geometry
            logger.info("Analyzing geometry...")
            analysis_result = await self.client.call_tool(
                "analyze_geometry",
                {
                    "check_connectivity": True,
                    "check_duplicates": True,
                    "tolerance": self.config.get("processing.tolerance", 0.001)
                }
            )
            workflow_result["steps"].append({
                "name": "analysis",
                "status": "success",
                "result": analysis_result
            })
            
            # Step 3: Convert based on output format
            if output_format == "ifc":
                # Convert to IFC
                logger.info("Converting to IFC...")
                ifc_result = await self.client.call_tool(
                    "convert_to_ifc",
                    {
                        "project_name": Path(input_file).stem,
                        "output_file": f"{Path(input_file).stem}.ifc"
                    }
                )
                workflow_result["steps"].append({
                    "name": "ifc_conversion",
                    "status": "success",
                    "result": ifc_result
                })
                
            elif output_format == "etabs":
                # Transfer to ETABS
                logger.info("Transferring to ETABS...")
                transfer_result = await self.client.call_tool(
                    "transfer_to_etabs",
                    {
                        "source": "autocad",
                        "material_mapping": options.get("material_mapping", {}),
                        "section_mapping": options.get("section_mapping", {})
                    }
                )
                workflow_result["steps"].append({
                    "name": "etabs_transfer",
                    "status": "success",
                    "result": transfer_result
                })
                
                # Export to Excel
                logger.info("Exporting ETABS Excel...")
                export_result = await self.client.call_tool(
                    "export_etabs_excel",
                    {
                        "filename": f"{Path(input_file).stem}_ETABS.xlsx"
                    }
                )
                workflow_result["steps"].append({
                    "name": "excel_export",
                    "status": "success",
                    "result": export_result,
                    "output_file": export_result
                })
            
            workflow_result["status"] = "completed"
            
        except Exception as e:
            logger.error(f"Workflow error: {e}")
            workflow_result["status"] = "failed"
            workflow_result["errors"].append(str(e))
        
        # Save to history
        self.conversion_history.append({
            "timestamp": datetime.now().isoformat(),
            "workflow": workflow_result
        })
        
        return workflow_result
    
    async def batch_convert(
        self,
        input_files: List[str],
        output_format: str = "etabs"
    ) -> List[Dict]:
        """Batch convert multiple files"""
        results = []
        
        for input_file in input_files:
            logger.info(f"Processing file {len(results) + 1}/{len(input_files)}: {input_file}")
            result = await self.execute_workflow(input_file, output_format)
            results.append(result)
        
        return results

# ==================== GUI Application ====================

class BridgeGUI:
    """Tkinter GUI for AutoCAD-ETABS Bridge"""
    
    def __init__(self):
        self.config = BridgeConfig()
        self.workflow_manager = WorkflowManager(self.config)
        self.setup_gui()
    
    def setup_gui(self):
        """Setup GUI components"""
        self.root = tk.Tk()
        self.root.title("AutoCAD-ETABS Bridge Professional")
        self.root.geometry("900x700")
        
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Import AutoCAD", command=self.import_autocad)
        file_menu.add_command(label="Batch Convert", command=self.batch_convert)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Settings", command=self.show_settings)
        tools_menu.add_command(label="Layer Mapping", command=self.show_layer_mapping)
        tools_menu.add_command(label="Material Editor", command=self.show_material_editor)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Documentation", command=self.show_documentation)
        help_menu.add_command(label="About", command=self.show_about)
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Input section
        input_frame = ttk.LabelFrame(main_frame, text="Input", padding="10")
        input_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(input_frame, text="AutoCAD File:").grid(row=0, column=0, sticky=tk.W)
        self.input_file_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.input_file_var, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(input_frame, text="Browse", command=self.browse_input).grid(row=0, column=2)
        
        # Options section
        options_frame = ttk.LabelFrame(main_frame, text="Conversion Options", padding="10")
        options_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(options_frame, text="Output Format:").grid(row=0, column=0, sticky=tk.W)
        self.output_format_var = tk.StringVar(value="etabs")
        format_combo = ttk.Combobox(
            options_frame,
            textvariable=self.output_format_var,
            values=["etabs", "ifc", "both"],
            state="readonly"
        )
        format_combo.grid(row=0, column=1, sticky=tk.W, padx=5)
        
        ttk.Label(options_frame, text="Tolerance (m):").grid(row=1, column=0, sticky=tk.W)
        self.tolerance_var = tk.StringVar(value="0.001")
        ttk.Entry(options_frame, textvariable=self.tolerance_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        self.merge_duplicates_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Merge duplicate points",
            variable=self.merge_duplicates_var
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W)
        
        self.check_connectivity_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Check connectivity",
            variable=self.check_connectivity_var
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W)
        
        # Progress section
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        self.progress_var = tk.StringVar(value="Ready")
        ttk.Label(progress_frame, textvariable=self.progress_var).grid(row=0, column=0, sticky=tk.W)
        
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            mode='indeterminate'
        )
        self.progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Output section
        output_frame = ttk.LabelFrame(main_frame, text="Output Log", padding="10")
        output_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        self.output_text = tk.Text(output_frame, height=15, width=80)
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.output_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.output_text.configure(yscrollcommand=scrollbar.set)
        
        # Action buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)
        
        ttk.Button(
            button_frame,
            text="Convert",
            command=self.convert_file,
            style="Accent.TButton"
        ).grid(row=0, column=0, padx=5)
        
        ttk.Button(
            button_frame,
            text="Clear",
            command=self.clear_output
        ).grid(row=0, column=1, padx=5)
        
        ttk.Button(
            button_frame,
            text="Exit",
            command=self.root.quit
        ).grid(row=0, column=2, padx=5)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
    
    def browse_input(self):
        """Browse for input file"""
        filename = filedialog.askopenfilename(
            title="Select AutoCAD File",
            filetypes=[
                ("AutoCAD Files", "*.dxf *.dwg"),
                ("DXF Files", "*.dxf"),
                ("DWG Files", "*.dwg"),
                ("All Files", "*.*")
            ]
        )
        if filename:
            self.input_file_var.set(filename)
    
    def convert_file(self):
        """Convert the selected file"""
        input_file = self.input_file_var.get()
        
        if not input_file:
            messagebox.showerror("Error", "Please select an input file")
            return
        
        if not os.path.exists(input_file):
            messagebox.showerror("Error", f"File not found: {input_file}")
            return
        
        # Run conversion in separate thread
        thread = threading.Thread(target=self.run_conversion, args=(input_file,))
        thread.daemon = True
        thread.start()
    
    def run_conversion(self, input_file: str):
        """Run conversion in background thread"""
        try:
            # Update UI
            self.progress_var.set("Converting...")
            self.progress_bar.start()
            self.log_output(f"\n{'='*60}")
            self.log_output(f"Starting conversion: {os.path.basename(input_file)}")
            self.log_output(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.log_output(f"{'='*60}\n")
            
            # Create event loop for async operations
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Execute workflow
            options = {
                "tolerance": float(self.tolerance_var.get()),
                "merge_duplicates": self.merge_duplicates_var.get(),
                "check_connectivity": self.check_connectivity_var.get()
            }
            
            result = loop.run_until_complete(
                self.workflow_manager.execute_workflow(
                    input_file,
                    self.output_format_var.get(),
                    options
                )
            )
            
            # Process result
            if result["status"] == "completed":
                self.log_output("\n✓ Conversion completed successfully!")
                
                for step in result["steps"]:
                    self.log_output(f"\n{step['name'].upper()}:")
                    if isinstance(step.get('result'), list):
                        for item in step['result']:
                            if hasattr(item, 'text'):
                                self.log_output(item.text)
                    
                    if 'output_file' in step:
                        self.log_output(f"\nOutput file: {step['output_file']}")
                
                messagebox.showinfo("Success", "Conversion completed successfully!")
            else:
                self.log_output(f"\n✗ Conversion failed: {result.get('errors', ['Unknown error'])}")
                messagebox.showerror("Error", "Conversion failed. Check the log for details.")
            
        except Exception as e:
            self.log_output(f"\n✗ Error: {str(e)}")
            messagebox.showerror("Error", f"Conversion error: {str(e)}")
        
        finally:
            # Reset UI
            self.progress_bar.stop()
            self.progress_var.set("Ready")
    
    def batch_convert(self):
        """Batch convert multiple files"""
        files = filedialog.askopenfilenames(
            title="Select AutoCAD Files",
            filetypes=[
                ("AutoCAD Files", "*.dxf *.dwg"),
                ("All Files", "*.*")
            ]
        )
        
        if not files:
            return
        
        # Show batch dialog
        batch_dialog = tk.Toplevel(self.root)
        batch_dialog.title("Batch Conversion")
        batch_dialog.geometry("500x300")
        
        ttk.Label(batch_dialog, text=f"Selected {len(files)} files for conversion").pack(pady=10)
        
        listbox = tk.Listbox(batch_dialog, height=10)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for file in files:
            listbox.insert(tk.END, os.path.basename(file))
        
        def start_batch():
            batch_dialog.destroy()
            thread = threading.Thread(target=self.run_batch_conversion, args=(files,))
            thread.daemon = True
            thread.start()
        
        ttk.Button(batch_dialog, text="Start Conversion", command=start_batch).pack(pady=10)
    
    def run_batch_conversion(self, files: List[str]):
        """Run batch conversion"""
        try:
            self.log_output(f"\n{'='*60}")
            self.log_output(f"Batch conversion: {len(files)} files")
            self.log_output(f"{'='*60}\n")
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            results = loop.run_until_complete(
                self.workflow_manager.batch_convert(
                    files,
                    self.output_format_var.get()
                )
            )
            
            # Summary
            successful = sum(1 for r in results if r["status"] == "completed")
            self.log_output(f"\nBatch conversion complete:")
            self.log_output(f"  Successful: {successful}/{len(files)}")
            
            if successful == len(files):
                messagebox.showinfo("Success", f"All {len(files)} files converted successfully!")
            else:
                messagebox.showwarning(
                    "Partial Success",
                    f"{successful} of {len(files)} files converted successfully."
                )
            
        except Exception as e:
            self.log_output(f"\nBatch conversion error: {str(e)}")
            messagebox.showerror("Error", f"Batch conversion failed: {str(e)}")
    
    def show_settings(self):
        """Show settings dialog"""
        settings_dialog = tk.Toplevel(self.root)
        settings_dialog.title("Settings")
        settings_dialog.geometry("400x300")
        
        # Settings tabs
        notebook = ttk.Notebook(settings_dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # General tab
        general_frame = ttk.Frame(notebook)
        notebook.add(general_frame, text="General")
        
        ttk.Label(general_frame, text="Output Directory:").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        output_dir_var = tk.StringVar(value=self.config.get("etabs.output_directory"))
        ttk.Entry(general_frame, textvariable=output_dir_var, width=30).grid(row=0, column=1, padx=10, pady=5)
        
        # Processing tab
        processing_frame = ttk.Frame(notebook)
        notebook.add(processing_frame, text="Processing")
        
        ttk.Label(processing_frame, text="Default Tolerance (m):").grid(row=0, column=0, sticky=tk.W, padx=10, pady=5)
        tolerance_var = tk.StringVar(value=self.config.get("processing.tolerance"))
        ttk.Entry(processing_frame, textvariable=tolerance_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=10, pady=5)
        
        ttk.Label(processing_frame, text="Merge Distance (m):").grid(row=1, column=0, sticky=tk.W, padx=10, pady=5)
        merge_var = tk.StringVar(value=self.config.get("processing.merge_distance"))
        ttk.Entry(processing_frame, textvariable=merge_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        
        def save_settings():
            self.config.set("etabs.output_directory", output_dir_var.get())
            self.config.set("processing.tolerance", float(tolerance_var.get()))
            self.config.set("processing.merge_distance", float(merge_var.get()))
            self.config.save_config()
            settings_dialog.destroy()
            messagebox.showinfo("Settings", "Settings saved successfully")
        
        ttk.Button(settings_dialog, text="Save", command=save_settings).pack(pady=10)
    
    def show_layer_mapping(self):
        """Show layer mapping dialog"""
        mapping_dialog = tk.Toplevel(self.root)
        mapping_dialog.title("Layer Mapping")
        mapping_dialog.geometry("500x400")
        
        ttk.Label(mapping_dialog, text="Map AutoCAD layers to structural elements:").pack(pady=10)
        
        # Create mapping table
        tree = ttk.Treeview(mapping_dialog, columns=("Layer", "Element"), show="headings")
        tree.heading("Layer", text="AutoCAD Layer")
        tree.heading("Element", text="Structural Element")
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Load current mappings
        layer_mapping = self.config.get("autocad.layer_mapping", {})
        for layer, element in layer_mapping.items():
            tree.insert("", tk.END, values=(layer, element))
        
        # Add/Edit buttons
        button_frame = ttk.Frame(mapping_dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Add").grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Edit").grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="Delete").grid(row=0, column=2, padx=5)
        ttk.Button(button_frame, text="Close", command=mapping_dialog.destroy).grid(row=0, column=3, padx=5)
    
    def show_material_editor(self):
        """Show material editor dialog"""
        material_dialog = tk.Toplevel(self.root)
        material_dialog.title("Material Editor")
        material_dialog.geometry("600x400")
        
        # Material list
        ttk.Label(material_dialog, text="Define materials for structural analysis:").pack(pady=10)
        
        # Create material table
        tree = ttk.Treeview(
            material_dialog,
            columns=("Name", "Type", "E", "Poisson", "Density"),
            show="headings"
        )
        tree.heading("Name", text="Name")
        tree.heading("Type", text="Type")
        tree.heading("E", text="E (GPa)")
        tree.heading("Poisson", text="Poisson")
        tree.heading("Density", text="Density (kg/m³)")
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Default materials
        materials = [
            ("CONCRETE", "Concrete", 30, 0.2, 2400),
            ("STEEL", "Steel", 200, 0.3, 7850),
            ("TIMBER", "Timber", 12, 0.35, 600)
        ]
        
        for mat in materials:
            tree.insert("", tk.END, values=mat)
        
        ttk.Button(material_dialog, text="Close", command=material_dialog.destroy).pack(pady=10)
    
    def show_documentation(self):
        """Show documentation"""
        doc_window = tk.Toplevel(self.root)
        doc_window.title("Documentation")
        doc_window.geometry("700x500")
        
        text = tk.Text(doc_window, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        
        documentation = """
AutoCAD-ETABS Bridge Professional Documentation
================================================

Overview:
---------
This application provides seamless conversion of AutoCAD drawings to ETABS structural 
analysis models using advanced geometry transformation techniques.

Features:
---------
• Direct DXF/DWG import with layer recognition
• IFC intermediate format support (IFC4 standard)
• Advanced geometry transformation (BREP, Swept Solid, CSG)
• ETABS Excel export with proper database structure
• Automatic structural element classification
• Material and section property mapping
• Batch conversion support

Workflow:
---------
1. Import AutoCAD file (DXF/DWG)
2. Automatic element classification based on layers
3. Geometry analysis and validation
4. Conversion to target format (ETABS/IFC)
5. Export to Excel for ETABS import

Layer Naming Convention:
------------------------
• S-COLS: Columns
• S-BEAM: Beams
• S-SLAB: Slabs
• S-WALL: Walls
• S-FNDN: Foundations

Tips:
-----
• Use standard layer names for automatic classification
• Set appropriate tolerance for geometry merging
• Check connectivity before export
• Review material assignments before conversion

For more information, visit: https://github.com/your-repo
        """
        
        text.insert(tk.END, documentation)
        text.config(state=tk.DISABLED)
    
    def show_about(self):
        """Show about dialog"""
        about_text = """
AutoCAD-ETABS Bridge Professional
Version 2.0.0

Advanced CAD to Structural Analysis Converter
Based on Enhanced Open-Source Approach (E-OSA)

Features state-of-the-art geometry transformation
algorithms for seamless CAD-BIM integration.

© 2024 Structural Engineering Integration Team
        """
        messagebox.showinfo("About", about_text)
    
    def log_output(self, message: str):
        """Log message to output text widget"""
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_output(self):
        """Clear output log"""
        self.output_text.delete(1.0, tk.END)
    
    def run(self):
        """Run the GUI application"""
        self.root.mainloop()

# ==================== CLI Interface ====================

class BridgeCLI:
    """Command-line interface for AutoCAD-ETABS Bridge"""
    
    def __init__(self):
        self.config = BridgeConfig()
        self.workflow_manager = WorkflowManager(self.config)
    
    async def run_cli(self, args):
        """Run CLI with arguments"""
        if args.command == "convert":
            await self.convert_command(args)
        elif args.command == "batch":
            await self.batch_command(args)
        elif args.command == "config":
            self.config_command(args)
        else:
            print(f"Unknown command: {args.command}")
    
    async def convert_command(self, args):
        """Handle convert command"""
        print(f"Converting {args.input}...")
        
        result = await self.workflow_manager.execute_workflow(
            args.input,
            args.format,
            {
                "tolerance": args.tolerance,
                "merge_duplicates": args.merge
            }
        )
        
        if result["status"] == "completed":
            print("✓ Conversion completed successfully!")
            if "output_file" in result["steps"][-1]:
                print(f"Output: {result['steps'][-1]['output_file']}")
        else:
            print(f"✗ Conversion failed: {result.get('errors', ['Unknown error'])}")
    
    async def batch_command(self, args):
        """Handle batch command"""
        import glob
        files = glob.glob(args.pattern)
        
        if not files:
            print(f"No files matching pattern: {args.pattern}")
            return
        
        print(f"Found {len(files)} files for batch conversion")
        
        results = await self.workflow_manager.batch_convert(files, args.format)
        
        successful = sum(1 for r in results if r["status"] == "completed")
        print(f"\nBatch conversion complete: {successful}/{len(files)} successful")
    
    def config_command(self, args):
        """Handle config command"""
        if args.get:
            value = self.config.get(args.get)
            print(f"{args.get} = {value}")
        elif args.set:
            key, value = args.set.split("=", 1)
            self.config.set(key, value)
            self.config.save_config()
            print(f"Set {key} = {value}")
        else:
            print("Current configuration:")
            print(json.dumps(self.config.config, indent=2))

# ==================== Main Entry Point ====================

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="AutoCAD-ETABS Bridge Professional"
    )
    
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch GUI interface"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Convert command
    convert_parser = subparsers.add_parser("convert", help="Convert single file")
    convert_parser.add_argument("input", help="Input AutoCAD file")
    convert_parser.add_argument(
        "--format",
        choices=["etabs", "ifc", "both"],
        default="etabs",
        help="Output format"
    )
    convert_parser.add_argument(
        "--tolerance",
        type=float,
        default=0.001,
        help="Geometry tolerance"
    )
    convert_parser.add_argument(
        "--merge",
        action="store_true",
        help="Merge duplicate points"
    )
    
    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Batch convert files")
    batch_parser.add_argument("pattern", help="File pattern (e.g., *.dxf)")
    batch_parser.add_argument(
        "--format",
        choices=["etabs", "ifc", "both"],
        default="etabs",
        help="Output format"
    )
    
    # Config command
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument("--get", help="Get configuration value")
    config_parser.add_argument("--set", help="Set configuration value (key=value)")
    
    args = parser.parse_args()
    
    if args.gui or (not args.command and not sys.stdin.isatty()):
        # Launch GUI
        app = BridgeGUI()
        app.run()
    elif args.command:
        # Run CLI
        cli = BridgeCLI()
        asyncio.run(cli.run_cli(args))
    else:
        # Show help
        parser.print_help()

if __name__ == "__main__":
    main()
