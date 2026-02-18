# autocad_2024_mcp_server.py
"""MCP Server for AutoCAD 2024 with Construction AI Integration"""

import asyncio
import logging
import sys
import math
import json
import time
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import win32com.client
import pythoncom
import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions
from house import create_complete_house
from shear_wall.building_dataframe_simple import recreate_in_autocad as create_simple_building
from shear_wall.building_dataframe import create_shear_wall_building
from shear_wall.building_dataframe_simple import recreate_with_mcp_connection

# Import New Modules for Standards and Extraction
try:
    from standards_module import StandardsManager
    from response_module import ResponseFormatter
    from extraction_module import EntityExtractor
    from validation_module import GeometryValidator, StandardsValidator
    from unit_coordinate_module import UnitConverter, CoordinateTransformer
    NEW_MODULES_AVAILABLE = True
    logging.info("New modules (standards, extraction, response) loaded successfully")
except ImportError as e:
    logging.warning(f"New modules not available: {e}")
    NEW_MODULES_AVAILABLE = False

# Import Construction AI modules
try:
    from construction_ai_modules.construction_sequencing import AIConstructionSequencer, ConstructionSequence
    from construction_ai_modules.construction_pattern_learner import ConstructionPatternLearner
    from construction_ai_modules.construction_validation import AIConstructionValidator
    from construction_ai_modules.construction_ai_logger import ConstructionAILogger
    CONSTRUCTION_AI_AVAILABLE = True
    logging.info("Construction AI modules loaded successfully")
except ImportError as e:
    logging.warning(f"Construction AI modules not available: {e}")
    CONSTRUCTION_AI_AVAILABLE = False

# Import Visualization and Report modules
try:
    from visualization_report_module.visualization_report_module import ComprehensiveConstructionReportGenerator
    # Import custom modern Gantt chart with engineering metrics
    try:
        from visualization_report_module.modern_gantt_with_metrics import ModernConstructionGantt
        MODERN_GANTT_AVAILABLE = True
        logging.info("Modern Gantt with metrics module loaded successfully")
    except ImportError:
        MODERN_GANTT_AVAILABLE = False
        logging.warning("Modern Gantt with metrics not available")
    # Keep old modules for backward compatibility if they exist
    try:
        from visualization_report_module.construction_analysis_engine import ConstructionAnalyzer
        from visualization_report_module.report_and_visualization import ConstructionReportGenerator
        OLD_VISUALIZATION_AVAILABLE = True
    except:
        OLD_VISUALIZATION_AVAILABLE = False
    VISUALIZATION_MODULE_AVAILABLE = True
    logging.info("Visualization & Report modules loaded successfully")
except ImportError as e:
    logging.warning(f"Visualization modules not available: {e}")
    VISUALIZATION_MODULE_AVAILABLE = False
    OLD_VISUALIZATION_AVAILABLE = False
    MODERN_GANTT_AVAILABLE = False


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)

# ============================================================================
# EXTRACTION DATA STORAGE - Prevent chat flooding
# ============================================================================
import os
from pathlib import Path


# ============================================================================
# COM RETRY HELPER - Handle "Call was rejected by callee" errors
# ============================================================================
def com_retry(func, max_retries=3, delay=0.5):
    """
    Retry a COM operation with exponential backoff.
    Handles 'Call was rejected by callee' errors (-2147418111).
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            error_str = str(e)
            # Check for COM rejection error
            if "-2147418111" in error_str or "rejected by callee" in error_str.lower():
                wait_time = delay * (2 ** attempt)
                logging.warning(f"[COM RETRY] Attempt {attempt + 1}/{max_retries} failed, waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
                # Pump COM messages to allow AutoCAD to process
                pythoncom.PumpWaitingMessages()
            else:
                # Non-retryable error
                raise
    # All retries exhausted
    raise last_error


def save_extraction_to_file(entities, extraction_result, extraction_type="all", autocad=None):
    """
    Save extracted entities to construction_reports/extraction_{building_name}_{timestamp}/ directory.
    Returns summary only, not full entity list.
    """
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Get building name from autocad if available
        building_name = 'unnamed'
        if autocad and autocad.connected and autocad.doc:
            building_name = autocad.doc.Name.replace('.dwg', '').replace(' ', '_')
        
        # HARDCODED: Always save to MCP server's construction_reports directory
        server_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = Path(os.path.join(server_dir, 'construction_reports'))
        extraction_dir = base_dir / f"extraction_{building_name}_{timestamp}"
        extraction_dir.mkdir(parents=True, exist_ok=True)
        
        bounds_data = {}
        layer_summary_data = {}
        unit_system_data = {}
        
        if 'bounds' in extraction_result:
            bounds_data = extraction_result['bounds']
        if 'layer_summary' in extraction_result:
            layer_summary_data = extraction_result['layer_summary']
        if 'unit_system' in extraction_result:
            unit_system_data = extraction_result['unit_system']
        
        full_data = {
            'extraction_time': timestamp,
            'extraction_type': extraction_type,
            'entity_count': len(entities),
            'bounds': bounds_data,
            'layer_summary': layer_summary_data,
            'unit_system': unit_system_data,
            'entities': entities
        }
        
        entities_file = extraction_dir / "entities.json"
        with open(entities_file, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, indent=2, ensure_ascii=False)
        
        summary_data = {
            'extraction_time': timestamp,
            'extraction_type': extraction_type,
            'entity_count': len(entities),
            'bounds': bounds_data,
            'layer_summary': layer_summary_data,
            'unit_system': unit_system_data
        }
        
        summary_file = extraction_dir / "summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)
        
        layer_counts = {}
        if layer_summary_data:
            for layer_name, layer_info in layer_summary_data.items():
                if isinstance(layer_info, dict) and 'count' in layer_info:
                    layer_counts[layer_name] = layer_info['count']
        
        unit_system_str = 'metric'
        if unit_system_data and 'system' in unit_system_data:
            unit_system_str = unit_system_data['system']
        
        summary_response = {
            'success': True,
            'entity_count': len(entities),
            'saved_to': str(extraction_dir),
            'files': ['entities.json', 'summary.json'],
            'layer_summary': layer_counts,
            'bounds': bounds_data,
            'unit_system': unit_system_str,
            'message': f"[OK] Extracted {len(entities)} entities - Data saved to: {extraction_dir}"
        }
        
        logging.info(f"[EXTRACTION] Saved {len(entities)} entities to {extraction_dir}")
        
        return summary_response
        
    except Exception as e:
        logging.error(f"[EXTRACTION] Failed to save: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'message': f"[ERROR] Failed to save extraction data: {str(e)}"
        }


class AutoCADController:
    """AutoCAD 2024 COM Automation Controller"""
    
    def __init__(self):
        self.acad = None
        self.doc = None
        self.model_space = None
        self.connected = False
        self.current_building_data = {}  # Store building data for analysis
        
    def connect(self) -> Tuple[bool, str]:
        """Connect to AutoCAD 2024"""
        try:
            pythoncom.CoInitialize()
            
            # Try to get running instance
            try:
                self.acad = win32com.client.GetActiveObject("AutoCAD.Application.24.3")
                message = "Connected to running AutoCAD 2024"
            except:
                # Start new instance
                self.acad = win32com.client.Dispatch("AutoCAD.Application.24.3")
                self.acad.Visible = True
                message = "Started new AutoCAD 2024 instance"
            
            # Get active document or create new
            if self.acad.Documents.Count == 0:
                self.doc = self.acad.Documents.Add()
            else:
                self.doc = self.acad.ActiveDocument
                
            self.model_space = self.doc.ModelSpace
            self.connected = True
            
            return True, f"[OK] {message}"
            
        except Exception as e:
            return False, f"[ERROR] Failed to connect: {str(e)}"
    
    def new_drawing(self):
        """Create new drawing"""
        if not self.connected:
            return False
            
        self.doc = self.acad.Documents.Add()
        self.model_space = self.doc.ModelSpace
        return True
    
    def draw_line(self, start: List[float], end: List[float]):
        """Draw a line"""
        start_point = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, start)
        end_point = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, end)
        return self.model_space.AddLine(start_point, end_point)
    
    def draw_circle(self, center: List[float], radius: float):
        """Draw a circle"""
        center_point = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, center)
        return self.model_space.AddCircle(center_point, radius)
    
    def draw_rectangle(self, corner1: List[float], corner2: List[float]):
        """Draw a rectangle using polyline"""
        points = [
            corner1[0], corner1[1], 0,
            corner2[0], corner1[1], 0,
            corner2[0], corner2[1], 0,
            corner1[0], corner2[1], 0,
            corner1[0], corner1[1], 0
        ]
        points_variant = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, points)
        pline = self.model_space.AddPolyline(points_variant)
        return pline
    
    def create_layer(self, name: str, color: int = 7):
        """Create a new layer"""
        try:
            layer = self.doc.Layers.Add(name)
            layer.Color = color
            return layer
        except:
            # Layer might already exist
            return self.doc.Layers.Item(name)
    
    def set_current_layer(self, name: str):
        """Set current layer"""
        self.doc.ActiveLayer = self.doc.Layers.Item(name)
    
    def zoom_extents(self):
        """Zoom to show all objects"""
        self.acad.ZoomExtents()
    
    def create_building_2d(self, length: float, width: float, 
                          bay_x: float, bay_y: float):
        """Create 2D building grid"""
        # Create layers
        self.create_layer("Grid", 8)  # Gray
        self.create_layer("Columns", 1)  # Red
        self.create_layer("Walls", 3)  # Green
        
        # Draw grid lines
        self.set_current_layer("Grid")
        
        # Vertical grid lines
        x = 0
        while x <= length:
            self.draw_line([x, 0, 0], [x, width, 0])
            x += bay_x
            
        # Horizontal grid lines
        y = 0
        while y <= width:
            self.draw_line([0, y, 0], [length, y, 0])
            y += bay_y
            
        # Draw columns at intersections
        self.set_current_layer("Columns")
        x = 0
        while x <= length:
            y = 0
            while y <= width:
                # Draw column as rectangle (600x600mm)
                col_size = 0.6
                corner1 = [x - col_size/2, y - col_size/2, 0]
                corner2 = [x + col_size/2, y + col_size/2, 0]
                self.draw_rectangle(corner1, corner2)
                y += bay_y
            x += bay_x
            
        # Draw outer walls
        self.set_current_layer("Walls")
        wall_thickness = 0.2
        
        # Outer boundary
        self.draw_rectangle(
            [-wall_thickness/2, -wall_thickness/2, 0],
            [length + wall_thickness/2, width + wall_thickness/2, 0]
        )
        
        self.zoom_extents()
        
    def create_3d_building(self, floors: int, length: float, width: float,
                          bay_x: float, bay_y: float, floor_height: float = 3.5):
        """Create 3D building model"""
        # Setup 3D view
        self.doc.SendCommand("-VPOINT 1,-1,1 ")
        self.doc.SendCommand("_ZOOM E ")
        self.doc.SendCommand("_SHADEMODE G ")
        
        # Create layers for 3D objects
        layers = {
            "3D_Columns": 1,    # Red
            "3D_Beams": 3,      # Green  
            "3D_Slabs": 8,      # Gray
        }
        
        for name, color in layers.items():
            self.create_layer(name, color)
        
        # Calculate grid
        nx = int(length / bay_x) + 1
        ny = int(width / bay_y) + 1
        
        # Create columns
        self.set_current_layer("3D_Columns")
        column_count = 0
        
        for i in range(nx):
            x = i * bay_x
            for j in range(ny):
                y = j * bay_y
                # Create column as 3D box
                cmd = f"_BOX {x-0.3},{y-0.3},0 {x+0.3},{y+0.3},{floors * floor_height} "
                self.doc.SendCommand(cmd)
                column_count += 1
        
        # Create floor slabs
        self.set_current_layer("3D_Slabs")
        for floor in range(1, floors + 1):
            z = floor * floor_height
            # Create slab
            cmd = f"_BOX 0,0,{z-0.2} {length},{width},{z} "
            self.doc.SendCommand(cmd)
            
        # Create beams
        self.set_current_layer("3D_Beams")
        beam_count = 0
        
        for floor in range(1, floors + 1):
            z = floor * floor_height
            
            # X-direction beams
            for j in range(ny):
                y = j * bay_y
                for i in range(nx - 1):
                    x1 = i * bay_x
                    x2 = (i + 1) * bay_x
                    # Beam along X
                    cmd = f"_BOX {x1},{y-0.2},{z-0.6} {x2},{y+0.2},{z} "
                    self.doc.SendCommand(cmd)
                    beam_count += 1
                    
            # Y-direction beams  
            for i in range(nx):
                x = i * bay_x
                for j in range(ny - 1):
                    y1 = j * bay_y
                    y2 = (j + 1) * bay_y
                    # Beam along Y
                    cmd = f"_BOX {x-0.2},{y1},{z-0.6} {x+0.2},{y2},{z} "
                    self.doc.SendCommand(cmd)
                    beam_count += 1
        
        self.zoom_extents()
        
        return {
            "columns": column_count,
            "beams": beam_count,
            "slabs": floors
        }
        
    def create_3d_building(self, floors: int, length: float, width: float,
                          bay_x: float, bay_y: float, floor_height: float = 3.5):
        """Create 3D building model"""
        # Switch to 3D view
        self.doc.SendCommand("-VPOINT 1,1,1 ")
        self.doc.SendCommand("_VISUALSTYLES C ")
        
        # Create layers
        self.create_layer("3D_Structure", 7)
        self.create_layer("3D_Floors", 8)
        
        self.set_current_layer("3D_Structure")
        
        # Create columns
        x = 0
        while x <= length:
            y = 0
            while y <= width:
                # Create 3D column (box)
                corner1 = [x - 0.3, y - 0.3, 0]
                corner2 = [x + 0.3, y + 0.3, floors * floor_height]
                
                # Use AddBox command through SendCommand
                cmd = f"_BOX {x-0.3},{y-0.3},0 {x+0.3},{y+0.3},{floors * floor_height} "
                self.doc.SendCommand(cmd)
                
                y += bay_y
            x += bay_x
            
        # Create floor slabs
        self.set_current_layer("3D_Floors")
        for floor in range(1, floors + 1):
            z = floor * floor_height
            # Create slab as 3D face or box
            cmd = f"_BOX 0,0,{z-0.2} {length},{width},{z} "
            self.doc.SendCommand(cmd)
            
        self.zoom_extents()
        
    def save_drawing(self, filename: str):
        """Save the drawing"""
        if not filename.endswith('.dwg'):
            filename += '.dwg'
        self.doc.SaveAs(filename)
        return filename
    
    def save_as_dxf(self, filename: str):
        """Save the drawing as DXF"""
        if not filename.endswith('.dxf'):
            filename += '.dxf'
        
        import os
        full_path = os.path.abspath(filename)
        
        # Save as AutoCAD 2018 DXF
        self.doc.SaveAs(full_path, 25)  # 25 = DXF format
        return full_path
    
    def extract_building_data(self) -> Dict:
        """Extract ACTUAL building data from AutoCAD model with REAL volume calculations.
        Uses COM retry logic to handle 'Call was rejected by callee' errors.
        """
        if not self.connected:
            return {'error': 'Not connected to AutoCAD', 'volumes_calculated': False}
        
        try:
            building_data = {
                'name': self.doc.Name.replace('.dwg', ''),
                'timestamp': datetime.now().isoformat(),
                'elements': {
                    'walls': [],
                    'slabs': [],
                    'columns': [],
                    'beams': []
                },
                'layers': {},
                'bounds': {},
                'statistics': {},
                'volumes': {
                    'total_volume': 0,
                    'wall_volume': 0,
                    'slab_volume': 0,
                    'column_volume': 0
                },
                'material_quantities': {},
                'bounds_valid': False,
                'volumes_calculated': False
            }
            
            # Count objects by layer - WITH RETRY LOGIC
            layer_counts = {}
            total_3dfaces = 0
            total_polyfaces = 0
            
            # Wait for AutoCAD to be ready
            time.sleep(0.3)
            pythoncom.PumpWaitingMessages()
            
            # Get model space count with retry
            def get_model_space_count():
                return self.model_space.Count
            
            try:
                entity_count = com_retry(get_model_space_count, max_retries=5, delay=0.5)
                logging.info(f"Model space has {entity_count} entities")
            except Exception as e:
                logging.error(f"Failed to get model space count: {e}")
                building_data['error'] = f"Failed to access model space: {str(e)}"
                return building_data
            
            # Iterate through model space with retry for each entity
            for i in range(entity_count):
                try:
                    # Get entity with retry
                    def get_entity():
                        return self.model_space.Item(i)
                    
                    entity = com_retry(get_entity, max_retries=3, delay=0.2)
                    
                    # Get entity properties with retry
                    def get_entity_type():
                        return entity.ObjectName
                    
                    def get_entity_layer():
                        return entity.Layer
                    
                    entity_type = com_retry(get_entity_type, max_retries=3, delay=0.1)
                    layer = com_retry(get_entity_layer, max_retries=3, delay=0.1)
                    
                    if layer not in layer_counts:
                        layer_counts[layer] = {}
                    
                    if entity_type not in layer_counts[layer]:
                        layer_counts[layer][entity_type] = 0
                    
                    layer_counts[layer][entity_type] += 1
                    
                    # Count specific entity types
                    if entity_type == "AcDb3dFace":
                        total_3dfaces += 1
                        # Extract wall data if in wall layer
                        if 'WALL' in layer.upper():
                            coords = []
                            for j in range(4):  # 3D faces have 4 vertices
                                try:
                                    def get_coord():
                                        return entity.Coordinate(j)
                                    coord = com_retry(get_coord, max_retries=2, delay=0.1)
                                    coords.append([float(coord[0]), float(coord[1]), float(coord[2])])
                                except:
                                    pass
                            
                            if coords:
                                building_data['elements']['walls'].append({
                                    'type': '3dface',
                                    'layer': layer,
                                    'coordinates': coords
                                })
                        
                        # Extract slab data if in floor layer
                        elif 'FLOR' in layer.upper() or 'SLAB' in layer.upper():
                            coords = []
                            for j in range(4):
                                try:
                                    def get_coord():
                                        return entity.Coordinate(j)
                                    coord = com_retry(get_coord, max_retries=2, delay=0.1)
                                    coords.append([float(coord[0]), float(coord[1]), float(coord[2])])
                                except:
                                    pass
                            
                            if coords:
                                building_data['elements']['slabs'].append({
                                    'type': '3dface',
                                    'layer': layer,
                                    'coordinates': coords
                                })
                    
                    elif entity_type == "AcDbPolyFaceMesh":
                        total_polyfaces += 1
                        
                except Exception as e:
                    logging.debug(f"Skipping entity {i}: {e}")
                    continue
            
            building_data['layers'] = layer_counts
            building_data['statistics'] = {
                'total_3dfaces': total_3dfaces,
                'total_polyfaces': total_polyfaces,
                'total_entities': sum(sum(counts.values()) for counts in layer_counts.values())
            }
            
            logging.info(f"Extracted {building_data['statistics']['total_entities']} entities")
            
            # Calculate bounds - WITH RETRY AND ERROR HANDLING
            try:
                def get_extmin():
                    return self.doc.GetVariable("EXTMIN")
                
                def get_extmax():
                    return self.doc.GetVariable("EXTMAX")
                
                minpoint = com_retry(get_extmin, max_retries=5, delay=0.3)
                maxpoint = com_retry(get_extmax, max_retries=5, delay=0.3)
                
                width = maxpoint[0] - minpoint[0]
                length = maxpoint[1] - minpoint[1]
                height = maxpoint[2] - minpoint[2]
                
                # Validate bounds are reasonable
                if width <= 0 or length <= 0 or height <= 0:
                    raise ValueError(f"Invalid bounds: {width} x {length} x {height}")
                
                building_data['bounds'] = {
                    'min': [minpoint[0], minpoint[1], minpoint[2]],
                    'max': [maxpoint[0], maxpoint[1], maxpoint[2]],
                    'width': width,
                    'length': length,
                    'height': height
                }
                building_data['bounds_valid'] = True
                
                logging.info(f"Bounds: {width:.2f}m x {length:.2f}m x {height:.2f}m")
                
            except Exception as e:
                logging.error(f"Failed to calculate bounds: {e}")
                building_data['bounds'] = {}
                building_data['bounds_valid'] = False
                building_data['error'] = f"Bounds calculation failed: {str(e)}"
                return building_data
            
            # VOLUME CALCULATIONS
            try:
                # Get wall and slab thicknesses from stored building data
                wall_thickness = self.current_building_data.get('wall_thickness', 0.3)
                floor_thickness = self.current_building_data.get('floor_thickness', 0.2)
                
                # Calculate number of floors
                floors = max(1, int(height / 4.0))
                
                # 1. Calculate wall volumes from actual 3DFace geometry
                total_wall_volume = 0
                total_wall_area = 0
                
                for wall in building_data['elements']['walls']:
                    coords = wall['coordinates']
                    if len(coords) >= 3:
                        # Calculate area of wall face using cross product
                        v1 = [coords[1][i] - coords[0][i] for i in range(3)]
                        v2 = [coords[2][i] - coords[0][i] for i in range(3)]
                        
                        # Cross product
                        cross = [
                            v1[1]*v2[2] - v1[2]*v2[1],
                            v1[2]*v2[0] - v1[0]*v2[2],
                            v1[0]*v2[1] - v1[1]*v2[0]
                        ]
                        
                        # Area = 0.5 * |cross product|
                        area = 0.5 * math.sqrt(cross[0]**2 + cross[1]**2 + cross[2]**2)
                        total_wall_area += area
                        
                        # Volume = area * thickness
                        volume = area * wall_thickness
                        total_wall_volume += volume
                
                building_data['volumes']['wall_volume'] = total_wall_volume
                building_data['volumes']['wall_area'] = total_wall_area
                
                logging.info(f"Wall volume: {total_wall_volume:.2f} m3 from {len(building_data['elements']['walls'])} faces")
                
                # 2. Calculate slab volumes from actual geometry OR from bounds
                total_slab_volume = 0
                total_slab_area = 0
                
                # Try to calculate from actual slab faces
                for slab in building_data['elements']['slabs']:
                    coords = slab['coordinates']
                    if len(coords) >= 3:
                        v1 = [coords[1][i] - coords[0][i] for i in range(3)]
                        v2 = [coords[2][i] - coords[0][i] for i in range(3)]
                        
                        cross = [
                            v1[1]*v2[2] - v1[2]*v2[1],
                            v1[2]*v2[0] - v1[0]*v2[2],
                            v1[0]*v2[1] - v1[1]*v2[0]
                        ]
                        
                        area = 0.5 * math.sqrt(cross[0]**2 + cross[1]**2 + cross[2]**2)
                        total_slab_area += area
                        total_slab_volume += area * floor_thickness
                
                # If no slab faces found, estimate from bounds
                floor_area = width * length
                if total_slab_volume == 0:
                    # Assume foundation + floors
                    num_slabs = floors + 1  # Foundation + each floor
                    total_slab_volume = floor_area * floor_thickness * num_slabs
                    total_slab_area = floor_area * num_slabs
                    logging.info(f"Estimated slab volume from bounds: {total_slab_volume:.2f} m3")
                else:
                    logging.info(f"Slab volume from geometry: {total_slab_volume:.2f} m3")
                
                building_data['volumes']['slab_volume'] = total_slab_volume
                building_data['volumes']['slab_area'] = total_slab_area
                building_data['volumes']['floor_area'] = floor_area
                
                # 3. Total structural volume
                total_volume = total_wall_volume + total_slab_volume
                building_data['volumes']['total_volume'] = total_volume
                building_data['volumes_calculated'] = True
                
                logging.info(f"Total volume: {total_volume:.2f} m3")
                
                # 4. Validate volumes
                envelope_volume = width * length * height
                if total_volume > envelope_volume:
                    logging.warning(f"Structural volume ({total_volume:.2f}) exceeds envelope ({envelope_volume:.2f})")
                    building_data['volumes']['validation_warning'] = "Structural volume exceeds building envelope"
                elif total_volume < envelope_volume * 0.01:
                    logging.warning(f"Structural volume ({total_volume:.2f}) is very small compared to envelope ({envelope_volume:.2f})")
                    building_data['volumes']['validation_warning'] = "Structural volume is suspiciously small"
                else:
                    building_data['volumes']['validation_passed'] = True
                    logging.info(f"Volume validation passed ({total_volume/envelope_volume*100:.1f}% of envelope)")
                
                # MATERIAL QUANTITIES
                building_data['material_quantities'] = {
                    'concrete_volume_m3': total_volume,
                    'concrete_volume_per_floor_m3': total_volume / floors,
                    'wall_concrete_m3': total_wall_volume,
                    'slab_concrete_m3': total_slab_volume,
                    'total_design_volume_m3': total_wall_volume + total_slab_volume,
                    'formwork_area_m2': (total_wall_area * 2) + total_slab_area,
                    # ESTIMATED rebar quantities (typical industry practice)
                    # Walls: ~110 kg/m3 (range: 80-150)
                    # Slabs: ~90 kg/m3 (range: 70-120)
                    'rebar_tons': (total_wall_volume * 110 + total_slab_volume * 90) / 1000,
                    'floors': floors,
                    'floor_area_per_floor_m2': floor_area,
                    'wall_thickness_m': wall_thickness,
                    'floor_thickness_m': floor_thickness
                }
                
                logging.info(f"Material quantities calculated:")
                logging.info(f"   - Concrete: {total_volume:.2f} m3")
                logging.info(f"   - Formwork: {building_data['material_quantities']['formwork_area_m2']:.1f} m2")
                logging.info(f"   - Rebar: {building_data['material_quantities']['rebar_tons']:.2f} tons")
                
            except Exception as e:
                logging.error(f"Volume calculation failed: {e}")
                building_data['volumes']['calculation_error'] = str(e)
                building_data['volumes_calculated'] = False
            
            self.current_building_data = building_data
            return building_data
            
        except Exception as e:
            logging.error(f"Fatal error extracting building data: {e}")
            return {'error': str(e), 'volumes_calculated': False}


# Global AutoCAD instance
autocad = AutoCADController()

# Create MCP server
server = Server("autocad-2024")

# Initialize Construction AI modules if available
if CONSTRUCTION_AI_AVAILABLE:
    # Initialize AI modules
    construction_sequencer = AIConstructionSequencer()
    pattern_learner = ConstructionPatternLearner()
    construction_validator = AIConstructionValidator()
    ai_logger = ConstructionAILogger()
    
    logging.info("Construction AI modules initialized")
else:
    construction_sequencer = None
    pattern_learner = None
    construction_validator = None
    ai_logger = None

# Initialize Visualization modules if available
if OLD_VISUALIZATION_AVAILABLE:
    construction_analyzer = ConstructionAnalyzer()
    report_generator = ConstructionReportGenerator()
    # Ensure reports directory exists - HARDCODED to MCP server location
    import os
    server_dir = os.path.dirname(os.path.abspath(__file__))
    construction_reports_dir = os.path.join(server_dir, 'construction_reports')
    os.makedirs(construction_reports_dir, exist_ok=True)
    logging.info(f"Reports will be saved in: {construction_reports_dir}")
else:
    construction_analyzer = None
    report_generator = None

# Initialize New Modules if available
if NEW_MODULES_AVAILABLE:
    standards_manager = StandardsManager()
    response_formatter = ResponseFormatter()
    entity_extractor = EntityExtractor()
    geometry_validator = GeometryValidator()
    standards_validator = StandardsValidator()
    unit_converter = UnitConverter()
    coordinate_transformer = CoordinateTransformer()
    logging.info("New modules initialized (standards, extraction, response, validation, units)")
else:
    standards_manager = None
    response_formatter = None
    entity_extractor = None
    geometry_validator = None
    standards_validator = None
    unit_converter = None
    coordinate_transformer = None


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    tools = [
        types.Tool(
            name="connect_autocad",
            description="Connect to AutoCAD 2024",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="new_drawing",
            description="Create a new drawing",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="draw_line",
            description="Draw a line between two points",
            inputSchema={
                "type": "object",
                "properties": {
                    "start": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Start point [x, y, z]"
                    },
                    "end": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "End point [x, y, z]"
                    }
                },
                "required": ["start", "end"]
            }
        ),
        types.Tool(
            name="draw_circle",
            description="Draw a circle",
            inputSchema={
                "type": "object",
                "properties": {
                    "center": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Center point [x, y, z]"
                    },
                    "radius": {
                        "type": "number",
                        "description": "Circle radius"
                    }
                },
                "required": ["center", "radius"]
            }
        ),
        types.Tool(
            name="create_building_2d",
            description="Create a 2D building floor plan",
            inputSchema={
                "type": "object",
                "properties": {
                    "length": {
                        "type": "number",
                        "description": "Building length in meters"
                    },
                    "width": {
                        "type": "number",
                        "description": "Building width in meters"
                    },
                    "bay_spacing": {
                        "type": "number",
                        "description": "Grid bay spacing in meters",
                        "default": 6
                    }
                },
                "required": ["length", "width"]
            }
        ),
        types.Tool(
            name="create_3d_building",
            description="Create a 3D building model",
            inputSchema={
                "type": "object",
                "properties": {
                    "floors": {
                        "type": "integer",
                        "description": "Number of floors"
                    },
                    "length": {
                        "type": "number",
                        "description": "Building length in meters"
                    },
                    "width": {
                        "type": "number",
                        "description": "Building width in meters"
                    },
                    "bay_spacing": {
                        "type": "number",
                        "description": "Grid bay spacing in meters",
                        "default": 6
                    },
                    "floor_height": {
                        "type": "number",
                        "description": "Floor to floor height",
                        "default": 3.5
                    }
                },
                "required": ["floors", "length", "width"]
            }
        ),
        types.Tool(
            name="save_drawing",
            description="Save the current drawing",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Filename to save (without .dwg extension)"
                    }
                },
                "required": ["filename"]
            }
        ),
        types.Tool(
            name="zoom_extents",
            description="Zoom to show all objects",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        types.Tool(
            name="create_house",
            description="Create a complete house with all systems",
            inputSchema={
                "type": "object",
                "properties": {
                    "floors": {
                        "type": "integer",
                        "description": "Number of floors (1-3)",
                        "default": 2
                    },
                    "length": {
                        "type": "number",
                        "description": "House length in meters",
                        "default": 12.0
                    },
                    "width": {
                        "type": "number",
                        "description": "House width in meters",
                        "default": 10.0
                    },
                    "style": {
                        "type": "string",
                        "description": "House style",
                        "enum": ["modern", "traditional", "minimalist", "luxury", "compact"],
                        "default": "modern"
                    },
                    "bedrooms": {
                        "type": "integer",
                        "description": "Number of bedrooms",
                        "default": 3
                    },
                    "bathrooms": {
                        "type": "integer",
                        "description": "Number of bathrooms",
                        "default": 2
                    },
                    "include_garage": {
                        "type": "boolean",
                        "description": "Include attached garage",
                        "default": True
                    },
                    "include_pool": {
                        "type": "boolean",
                        "description": "Include swimming pool",
                        "default": False
                    },
                    "include_landscaping": {
                        "type": "boolean",
                        "description": "Include landscaping",
                        "default": True
                    },
                    "include_furniture": {
                        "type": "boolean",
                        "description": "Include furniture",
                        "default": True
                    },
                    "include_mep": {
                        "type": "boolean",
                        "description": "Include HVAC, electrical, plumbing",
                        "default": True
                    },
                    "include_basement": {
                        "type": "boolean",
                        "description": "Include basement",
                        "default": False
                    },
                    "has_office": {
                        "type": "boolean",
                        "description": "Include home office",
                        "default": False
                    },
                    "open_plan": {
                        "type": "boolean",
                        "description": "Open plan living area",
                        "default": True
                    }
                },
                "required": []
            }
        ),
        types.Tool(
            name="create_shear_wall_building",
            description="""Create a shear wall building in AutoCAD.
            
                    CRITICAL INSTRUCTION FOR KEYWORD DETECTION:
                    1. Scan the user's message for these keyword combinations:
                        - English: "simple" AND ("basic" OR "basics")
                        - Korean: "ë‹¨ìˆœ" AND ("ê¸°ë³¸" OR "ê¸°ë³¸ì ")
                        - OR the word "predefined"
                    2. If BOTH "simple" AND ("basic"/"basics") are found, OR "predefined" is found:
                    - MUST set building_type = "simple"
                    - MUST ignore ALL other parameters in the user's message
                    - DO NOT consider the presence of custom parameters
                    - DO NOT interpret user intent beyond keyword detection
                    3. Only if the above keywords are NOT found:
                    - Set building_type = "parametric"
                    - Use the custom parameters provided

                    EXAMPLE THAT MUST TRIGGER SIMPLE:
                    - "Design a simple Shear-Wall building with basic: -10 floors..."
                    - "ê¸°ë³¸ ì¡°ê±´ìœ¼ë¡œ ë‹¨ìˆœ ì „ë‹¨ë²½ ê±´ë¬¼ ì„¤ê³„: 10ì¸µ..."
                    â†’ Contains "simple" AND "basic" â†’ building_type = "simple" (ignore all numbers)

                    The keyword check takes absolute priority over any other reasoning
            
            When building_type is "simple", the function will recreate the exact reference building from building_dataframe_simple.py and all dimensional parameters are ignored.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "building_type": {
                        "type": "string",
                        "description": "MUST be 'simple' if user message contains 'simple'/'basic'/'predefined', otherwise 'parametric'",
                        "enum": ["simple", "parametric"]
                    },
                    "floors": {
                        "type": "integer",
                        "description": "Number of floors (only used when building_type is 'parametric')",
                        "default": 10
                    },
                    "length": {
                        "type": "number",
                        "description": "Building length in meters (only used when building_type is 'parametric')",
                        "default": 36.0
                    },
                    "width": {
                        "type": "number",
                        "description": "Building width in meters (only used when building_type is 'parametric')",
                        "default": 12.0
                    },
                    "floor_height": {
                        "type": "number",
                        "description": "Floor to floor height in meters (only used when building_type is 'parametric')",
                        "default": 4.0
                    },
                    "floor_thickness": {
                        "type": "number",
                        "description": "Floor slab thickness in meters (only used when building_type is 'parametric')",
                        "default": 0.2
                    },
                    "wall_thickness": {
                        "type": "number",
                        "description": "Wall thickness in meters (only used when building_type is 'parametric')",
                        "default": 0.3
                    },
                    "wall_length": {
                        "type": "number",
                        "description": "Individual wall length in meters (only used when building_type is 'parametric')",
                        "default": 2.0
                    },
                    "shear_wall_ratio": {
                        "type": "number",
                        "description": "Ratio of shear walls to perimeter 0.0-1.0 (only used when building_type is 'parametric')",
                        "default": 0.25
                    }
                },
                "required": ["building_type"]
            }
        ),
        types.Tool(
            name="save_as_dxf",
            description="Save the current drawing as DXF file",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Filename to save (without .dxf extension)"
                    }
                },
                "required": ["filename"]
            }
        )
    ]
    
    # Add Construction AI tools if available
    if CONSTRUCTION_AI_AVAILABLE:
        tools.extend([
            types.Tool(
                name="generate_construction_sequence",
                description="Generate AI-optimized construction sequence for building",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "building_data": {
                            "type": "object",
                            "description": "Building data including floors, area, structural system"
                        },
                        "optimization_mode": {
                            "type": "string",
                            "enum": ["time", "cost", "safety", "balanced"],
                            "description": "Optimization priority"
                        }
                    },
                    "required": ["building_data"]
                }
            ),
            types.Tool(
                name="validate_constructability",
                description="AI validation of constructability",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_data": {
                            "type": "object",
                            "description": "Complete project data"
                        },
                        "validate_all": {
                            "type": "boolean",
                            "description": "Run all validation checks"
                        }
                    },
                    "required": ["project_data"]
                }
            ),
            types.Tool(
                name="learn_patterns",
                description="Learn construction patterns from building dataset",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "buildings": {
                            "type": "array",
                            "description": "List of building data"
                        },
                        "batch_size": {
                            "type": "integer",
                            "description": "Processing batch size"
                        }
                    },
                    "required": ["buildings"]
                }
            ),
            types.Tool(
                name="get_ai_analytics",
                description="Get Construction AI analytics and performance",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Number of days for analytics"
                        }
                    }
                }
            )
        ])
    
    # Add Visualization and Report tools if available
    if VISUALIZATION_MODULE_AVAILABLE:
        tools.extend([
            types.Tool(
                name="generate_comprehensive_construction_report",
                description="Generate comprehensive construction report with standards validation and detailed logging. Saves to construction_reports/{building_name}_{timestamp}/. AI modules only used if explicitly requested.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "use_autocad_data": {
                            "type": "boolean",
                            "description": "Extract and use actual AutoCAD model data",
                            "default": True
                        },
                        "use_ai_modules": {
                            "type": "boolean",
                            "description": "Use Construction AI modules (sequencer, validator, pattern learner). Only enabled if explicitly set to true.",
                            "default": False
                        },
                        "output_dir": {
                            "type": "string",
                            "description": "Base output directory",
                            "default": "./construction_reports"
                        }
                    }
                }
            )
        ])
        
        # Add old visualization tools if available for backward compatibility
        if OLD_VISUALIZATION_AVAILABLE:
            tools.extend([
                types.Tool(
                    name="extract_building_data",
                    description="Extract ACTUAL building data from current AutoCAD model",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                types.Tool(
                    name="analyze_construction_real",
                    description="Analyze construction using ACTUAL AutoCAD geometry (not formulas)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "use_autocad_data": {
                                "type": "boolean",
                                "description": "Use real AutoCAD extracted data",
                                "default": True
                            }
                        }
                    }
                ),
                types.Tool(
                    name="generate_construction_report",
                    description="Generate professional PDF report with visualizations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "include_gantt": {
                                "type": "boolean",
                                "default": True
                            },
                            "include_costs": {
                                "type": "boolean",
                                "default": False
                            }
                        }
                    }
                )
            ])
    
    # Add New Module tools if available
    if NEW_MODULES_AVAILABLE:
        tools.extend([
            # ============ EXTRACTION TOOLS ============
            types.Tool(
                name="extract_all_entities_structured",
                description="Extract all entities with full metadata, units, coordinates, and standards mapping",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "unit_system": {
                            "type": "string",
                            "enum": ["metric", "imperial", "auto"],
                            "description": "Unit system for output",
                            "default": "auto"
                        },
                        "include_standards": {
                            "type": "boolean",
                            "description": "Include IFC4 and ETABS mappings",
                            "default": True
                        },
                        "include_geometry": {
                            "type": "boolean",
                            "description": "Include detailed geometry",
                            "default": True
                        }
                    }
                }
            ),
            types.Tool(
                name="extract_by_layer_structured",
                description="Extract entities from specific layer with structured output",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "layer_name": {
                            "type": "string",
                            "description": "Layer name (e.g., 'S-COLS', 'S-BEAM')"
                        },
                        "classify_elements": {
                            "type": "boolean",
                            "default": True
                        }
                    },
                    "required": ["layer_name"]
                }
            ),
            types.Tool(
                name="get_building_metadata",
                description="Get building-level metadata (bounds, units, coordinate system)",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            
            # ============ STANDARDS TOOLS ============
            types.Tool(
                name="query_standard",
                description="Query building standard specifications (ASCE 7-22, ACI 318, AISC 360, IFC4)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "standard": {
                            "type": "string",
                            "enum": ["ASCE_7_22", "ACI_318", "AISC_360", "IFC4", "RSMeans_2024"],
                            "description": "Standard to query"
                        },
                        "query_type": {
                            "type": "string",
                            "enum": ["material", "section", "load", "mapping", "info"],
                            "description": "Type of query"
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Query parameters (e.g., material_grade, section_name)"
                        }
                    },
                    "required": ["standard", "query_type"]
                }
            ),
            types.Tool(
                name="get_load_combinations",
                description="Get standard load combinations for ETABS",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "standard": {
                            "type": "string",
                            "enum": ["ASCE_7_22"],
                            "default": "ASCE_7_22"
                        },
                        "design_method": {
                            "type": "string",
                            "enum": ["LRFD", "ASD"],
                            "default": "LRFD"
                        }
                    }
                }
            ),
            types.Tool(
                name="map_to_ifc4",
                description="Map AutoCAD layers to IFC4 classes",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "layer_name": {
                            "type": "string",
                            "description": "Layer name to map"
                        }
                    },
                    "required": ["layer_name"]
                }
            ),
            types.Tool(
                name="get_construction_sequence_standard",
                description="Get standard construction sequence by building type",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "building_type": {
                            "type": "string",
                            "enum": ["concrete_frame", "steel_frame", "shear_wall"],
                            "description": "Building type"
                        },
                        "standard": {
                            "type": "string",
                            "default": "RSMeans_2024"
                        }
                    },
                    "required": ["building_type"]
                }
            ),
            
            # ============ VALIDATION TOOLS ============
            types.Tool(
                name="validate_for_export",
                description="Validate model is ready for ETABS/IFC export",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "target_format": {
                            "type": "string",
                            "enum": ["ETABS", "IFC4", "SAP2000"],
                            "description": "Export target format"
                        },
                        "check_connectivity": {
                            "type": "boolean",
                            "default": True
                        }
                    },
                    "required": ["target_format"]
                }
            ),
            types.Tool(
                name="check_geometry_quality",
                description="Validate geometry connectivity and topology",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "check_duplicates": {
                            "type": "boolean",
                            "default": True
                        },
                        "tolerance": {
                            "type": "number",
                            "default": 0.001
                        }
                    }
                }
            ),
            
            # ============ UNIT/COORDINATE TOOLS ============
            types.Tool(
                name="convert_units",
                description="Convert values between unit systems",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "value": {
                            "type": "number",
                            "description": "Value to convert"
                        },
                        "from_unit": {
                            "type": "string",
                            "description": "Source unit (e.g., 'ft', 'm', 'kip', 'kN')"
                        },
                        "to_unit": {
                            "type": "string",
                            "description": "Target unit"
                        },
                        "unit_type": {
                            "type": "string",
                            "enum": ["length", "force", "mass", "pressure"],
                            "default": "length"
                        }
                    },
                    "required": ["value", "from_unit", "to_unit"]
                }
            ),
            types.Tool(
                name="get_coordinate_system",
                description="Get current AutoCAD coordinate system info",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            
            # ============ STANDARDS QUERY TOOLS (NEW) ============
            types.Tool(
                name="query_aci_318_complete",
                description="Query ACI 318-19 complete (phi factors, concrete props, rebar, development length, beam shear)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_type": {
                            "type": "string",
                            "enum": ["phi_factor", "concrete_props", "rebar_props", 
                                    "development_length", "beam_shear"],
                            "description": "Type of query"
                        },
                        "member_type": {
                            "type": "string",
                            "description": "For phi_factor: 'moment', 'shear', 'torsion', etc."
                        },
                        "fc_psi": {
                            "type": "number",
                            "description": "Concrete compressive strength (psi)"
                        },
                        "fy_psi": {
                            "type": "number",
                            "description": "Rebar yield strength (psi)",
                            "default": 60000
                        },
                        "bar_size": {
                            "type": "string",
                            "description": "Bar size (e.g., '#8', '#10')"
                        },
                        "grade": {
                            "type": "string",
                            "description": "Rebar grade ('60', '75')"
                        },
                        "bw": {
                            "type": "number",
                            "description": "Beam width (inches)"
                        },
                        "d": {
                            "type": "number",
                            "description": "Effective depth (inches)"
                        }
                    },
                    "required": ["query_type"]
                }
            ),
            types.Tool(
                name="query_formwork",
                description="Query ACI 347-04 formwork design (loads, lateral pressure, removal times)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_type": {
                            "type": "string",
                            "enum": ["loads", "lateral_pressure", "removal_time"],
                            "description": "Type of query"
                        },
                        "use_motorized_carts": {
                            "type": "boolean",
                            "description": "For loads: use motorized carts",
                            "default": False
                        },
                        "placement_rate": {
                            "type": "number",
                            "description": "For lateral_pressure: placement rate (ft/hr)",
                            "default": 2.0
                        },
                        "temperature": {
                            "type": "number",
                            "description": "For lateral_pressure: temperature (Â°F)",
                            "default": 70
                        },
                        "concrete_height": {
                            "type": "number",
                            "description": "For lateral_pressure: concrete height (ft)",
                            "default": 10
                        },
                        "member_type": {
                            "type": "string",
                            "description": "For removal_time: 'slab', 'beam', 'column'"
                        }
                    },
                    "required": ["query_type"]
                }
            ),
            types.Tool(
                name="query_productivity",
                description="Query construction productivity rates and calculate labor durations",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query_type": {
                            "type": "string",
                            "enum": ["get_rate", "calculate_duration", "estimate_slab", 
                                    "list_categories", "list_tasks"],
                            "description": "Type of query"
                        },
                        "category": {
                            "type": "string",
                            "description": "For get_rate/list_tasks: 'excavation', 'concrete', 'rebar', 'masonry', 'plaster', 'road'"
                        },
                        "task": {
                            "type": "string",
                            "description": "For get_rate/calculate_duration: task name (e.g., 'manual_laying', 'fixing_slabs_footings')"
                        },
                        "quantity": {
                            "type": "number",
                            "description": "For calculate_duration: quantity of work"
                        },
                        "crew_size": {
                            "type": "integer",
                            "description": "For calculate_duration/estimate_slab: number of workers",
                            "default": 6
                        },
                        "area_m2": {
                            "type": "number",
                            "description": "For estimate_slab: slab area (mÂ²)"
                        },
                        "thickness_mm": {
                            "type": "number",
                            "description": "For estimate_slab: slab thickness (mm)"
                        }
                    },
                    "required": ["query_type"]
                }
            )
        ])
    
    return tools

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "connect_autocad":
            success, message = autocad.connect()
            return [types.TextContent(type="text", text=message)]
            
        elif name == "new_drawing":
            if not autocad.connected:
                return [types.TextContent(
                    type="text",
                    text="[ERROR] Please connect to AutoCAD first"
                )]
                
            autocad.new_drawing()
            return [types.TextContent(
                type="text",
                text="[OK] Created new drawing"
            )]
            
        elif name == "draw_line":
            if not autocad.connected:
                return [types.TextContent(
                    type="text",
                    text="[ERROR] Please connect to AutoCAD first"
                )]
                
            start = arguments["start"]
            end = arguments["end"]
            
            # Ensure 3D points
            if len(start) == 2:
                start.append(0)
            if len(end) == 2:
                end.append(0)
                
            autocad.draw_line(start, end)
            return [types.TextContent(
                type="text",
                text=f"[OK] Drew line from {start} to {end}"
            )]
            
        elif name == "draw_circle":
            if not autocad.connected:
                return [types.TextContent(
                    type="text",
                    text="[ERROR] Please connect to AutoCAD first"
                )]
                
            center = arguments["center"]
            radius = arguments["radius"]
            
            if len(center) == 2:
                center.append(0)
                
            autocad.draw_circle(center, radius)
            return [types.TextContent(
                type="text",
                text=f"[OK] Drew circle at {center} with radius {radius}"
            )]
            
        elif name == "create_building_2d":
            if not autocad.connected:
                return [types.TextContent(
                    type="text",
                    text="[ERROR] Please connect to AutoCAD first"
                )]
                
            length = arguments["length"]
            width = arguments["width"]
            bay = arguments.get("bay_spacing", 6)
            
            autocad.create_building_2d(length, width, bay, bay)
            
            n_bays_x = int(length / bay)
            n_bays_y = int(width / bay)
            
            return [types.TextContent(
                type="text",
                text=f"""[OK] Created 2D building plan:
- Size: {length}m x {width}m
- Grid: {n_bays_x + 1} x {n_bays_y + 1} lines
- Bay spacing: {bay}m
- Columns placed at grid intersections
- Layers created: Grid, Columns, Walls"""
            )]
            
        elif name == "create_3d_building":
            if not autocad.connected:
                return [types.TextContent(
                    type="text",
                    text="[ERROR] Please connect to AutoCAD first"
                )]
                
            floors = arguments["floors"]
            length = arguments["length"]
            width = arguments["width"]
            bay = arguments.get("bay_spacing", 6)
            floor_height = arguments.get("floor_height", 3.5)
            
            autocad.create_3d_building(floors, length, width, bay, bay, floor_height)
            
            return [types.TextContent(
                type="text",
                text=f"""[OK] Created 3D building model:
- Floors: {floors}
- Size: {length}m x {width}m x {floors * floor_height}m
- Columns and floor slabs created
- Switched to 3D view"""
            )]
            
        elif name == "save_drawing":
            if not autocad.connected:
                return [types.TextContent(
                    type="text",
                    text="[ERROR] Please connect to AutoCAD first"
                )]
                
            filename = arguments["filename"]
            autocad.save_drawing(filename)
            
            return [types.TextContent(
                type="text",
                text=f"[OK] Saved drawing as {filename}.dwg"
            )]
            
        elif name == "zoom_extents":
            if not autocad.connected:
                return [types.TextContent(
                    type="text",
                    text="[ERROR] Please connect to AutoCAD first"
                )]
                
            autocad.zoom_extents()
            return [types.TextContent(
                type="text",
                text="[OK] Zoomed to show all objects"
            )]
        ###new line here 
        elif name == "create_house":
            if not autocad.connected:
                return [types.TextContent(
                    type="text",
                    text="[ERROR] Please connect to AutoCAD first"
                )]
            
            try:
                result = create_complete_house(autocad, arguments)
                
                return [types.TextContent(
                    type="text",
                    text=result
                )]
            except Exception as e:
                logging.error(f"Error creating house: {e}", exc_info=True)
                return [types.TextContent(
                    type="text",
                    text=f"[ERROR] Error creating house: {str(e)}"
                )]
        ######## to here
        # 
        ###new   line ofr shear wall building 
        elif name == "create_shear_wall_building":
            if not autocad.connected:
                return [types.TextContent(
                    type="text",
                    text="[ERROR] Please connect to AutoCAD first"
                )]
            
            try:
                building_type = arguments.get('building_type', 'parametric')
                
                if building_type.lower() == 'simple':
                    recreate_with_mcp_connection(autocad)
                    result = "Simple building created from building_dataframe_simple.py"
                else:
                    result = create_shear_wall_building(autocad, arguments)
                
                # AUTO-SAVE the building with proper name immediately after creation
                try:
                    floors = arguments.get('floors', 10)
                    length = arguments.get('length', 36)
                    width = arguments.get('width', 12)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    
                    # Create descriptive filename
                    if building_type.lower() == 'simple':
                        filename = f"shear_wall_simple_{timestamp}"
                    else:
                        filename = f"shear_wall_{floors}floors_{int(length)}x{int(width)}m_{timestamp}"
                    
                    # Save the drawing
                    autocad.save_drawing(filename)
                    result += f"\n[AUTO-SAVED] Drawing saved as: {filename}.dwg"
                    logging.info(f"Building auto-saved as: {filename}.dwg")
                    
                except Exception as save_error:
                    logging.error(f"Failed to auto-save building: {save_error}")
                    result += f"\n[WARNING] Auto-save failed: {str(save_error)}"
                
                return [types.TextContent(type="text", text=result)]
                
            except Exception as e:
                logging.error(f"Error: {e}", exc_info=True)
                return [types.TextContent(type="text", text=f"[ERROR] {str(e)}")]
        
        
        elif name == "save_as_dxf":
            if not autocad.connected:
                return [types.TextContent(
                    type="text",
                    text="[ERROR] Please connect to AutoCAD first"
                )]
                
            filename = arguments["filename"]
            result_file = autocad.save_as_dxf(filename)
            
            return [types.TextContent(
                type="text",
                text=f"[OK] Saved drawing as {result_file}"
            )]

        ##to here
        
        # Construction AI Tools
        elif name == "generate_construction_sequence" and CONSTRUCTION_AI_AVAILABLE:
            building_data = arguments.get("building_data", {})
            optimization_mode = arguments.get("optimization_mode", "balanced")
            
            # Log the request
            if ai_logger:
                await ai_logger.log_chat_interaction(
                    f"Generate sequence for {building_data.get('name', 'building')}",
                    "Processing...",
                    ["generate_construction_sequence"],
                    0.0, 0.0
                )
            
            # Generate sequence
            sequence = await construction_sequencer.generate_sequence(
                building_data,
                optimization_mode=optimization_mode
            )
            
            # Log the result
            if ai_logger:
                await ai_logger.log_construction_sequence({
                    'project_name': sequence.project_name,
                    'floors': building_data.get('floors', 0),
                    'total_duration': sequence.total_duration,
                    'activities': sequence.activities,
                    'critical_path': sequence.critical_path,
                    'optimization_score': sequence.optimization_score,
                    'ai_confidence': sequence.ai_confidence
                })
            
            result = construction_sequencer.export_sequence_to_json(sequence)
            return [types.TextContent(type="text", text=result)]
            
        elif name == "validate_constructability" and CONSTRUCTION_AI_AVAILABLE:
            project_data = arguments.get("project_data", {})
            validate_all = arguments.get("validate_all", True)
            
            result = await construction_validator.validate_constructability(
                project_data,
                validate_all=validate_all
            )
            
            # Log validation
            if ai_logger:
                await ai_logger.log_validation_result({
                    'project_name': result.project_name,
                    'is_constructable': result.is_constructable,
                    'overall_score': result.overall_score,
                    'issues': [
                        {
                            'severity': issue.severity.value,
                            'category': issue.category,
                            'description': issue.description
                        }
                        for issue in result.issues
                    ],
                    'ai_recommendations': result.ai_recommendations
                })
            
            return [types.TextContent(
                type="text",
                text=json.dumps({
                    'constructable': result.is_constructable,
                    'score': result.overall_score,
                    'issues': len(result.issues),
                    'critical_issues': sum(1 for i in result.issues if i.severity.value == 'critical'),
                    'recommendations': result.ai_recommendations,
                    'risk_level': result.risk_assessment['overall_risk_level']
                }, indent=2)
            )]
            
        elif name == "learn_patterns" and CONSTRUCTION_AI_AVAILABLE:
            buildings = arguments.get("buildings", [])
            batch_size = arguments.get("batch_size", 100)
            
            results = await pattern_learner.learn_from_dataset(buildings, batch_size)
            
            # Log pattern discovery
            if ai_logger:
                for pattern_id, pattern in pattern_learner.patterns.items():
                    await ai_logger.log_pattern_discovery({
                        'id': pattern.id,
                        'pattern_type': pattern.pattern_type,
                        'frequency': pattern.frequency,
                        'confidence': pattern.confidence,
                        'building_characteristics': pattern.building_characteristics
                    })
            
            return [types.TextContent(
                type="text",
                text=json.dumps(results, indent=2, default=str)
            )]
            
        elif name == "get_ai_analytics" and CONSTRUCTION_AI_AVAILABLE:
            days = arguments.get("days", 7)
            
            if ai_logger:
                analytics = ai_logger.get_analytics(days)
                session_summary = ai_logger.get_session_summary()
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps({
                        'session': session_summary,
                        'analytics': analytics
                    }, indent=2, default=str)
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text="[ERROR] AI Logger not initialized"
                )]
        
        ##end Construction AI tools
        
        # ============ COMPREHENSIVE REPORT GENERATION ============
        elif name == "generate_comprehensive_construction_report" and VISUALIZATION_MODULE_AVAILABLE:
            if not autocad.connected and arguments.get('use_autocad_data', True):
                return [types.TextContent(type="text", text="[ERROR] Not connected to AutoCAD")]
            
            try:
                # Initialize autocad_data to avoid scope issues
                autocad_data = None
                
                # Helper functions for extraction folder management
                def find_most_recent_extraction():
                    """Find the most recent extraction folder (either extraction_{name}_{timestamp} or {name}_{timestamp})"""
                    try:
                        server_dir = os.path.dirname(os.path.abspath(__file__))
                        base_dir = Path(os.path.join(server_dir, 'construction_reports'))
                        
                        if not base_dir.exists():
                            return None
                        
                        # Find all directories with timestamp pattern
                        extraction_folders = [d for d in base_dir.iterdir() 
                                            if d.is_dir() and (d.name.startswith('extraction_') or '_202' in d.name)]
                        
                        if not extraction_folders:
                            return None
                        
                        extraction_folders.sort(reverse=True)
                        most_recent = extraction_folders[0]
                        
                        entities_file = most_recent / "entities.json"
                        if entities_file.exists():
                            return most_recent
                        
                        return None
                    except Exception as e:
                        logging.error(f"Error finding extraction folder: {e}")
                        return None
                
                def read_extraction_data(extraction_dir):
                    """Read building data from extraction_{timestamp} folder"""
                    try:
                        entities_file = extraction_dir / "entities.json"
                        
                        if not entities_file.exists():
                            return None
                        
                        with open(entities_file, 'r', encoding='utf-8') as f:
                            extraction_data = json.load(f)
                        
                        # Return raw_autocad_data if available (preferred)
                        if 'raw_autocad_data' in extraction_data:
                            return extraction_data['raw_autocad_data']
                        elif 'building_data' in extraction_data:
                            return extraction_data['building_data']
                        elif 'statistics' in extraction_data:
                            return extraction_data
                        else:
                            return None
                            
                    except Exception as e:
                        logging.error(f"Error reading extraction data: {e}")
                        return None
                
                def save_building_data_to_extraction(autocad_data):
                    """Save raw autocad_data to extraction_{building_name}_{timestamp} folder"""
                    try:
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        building_name = autocad_data.get('name', 'unnamed').replace(' ', '_')
                        server_dir = os.path.dirname(os.path.abspath(__file__))
                        base_dir = Path(os.path.join(server_dir, 'construction_reports'))
                        extraction_dir = base_dir / f"{building_name}_{timestamp}"
                        extraction_dir.mkdir(parents=True, exist_ok=True)
                        
                        logging.info(f"[EXTRACTION] Saving to directory: {extraction_dir}")
                        
                        # Extract data from autocad_data (matches save_extraction_to_file format)
                        bounds_data = autocad_data.get('bounds', {})
                        layers_data = autocad_data.get('layers', {})
                        statistics_data = autocad_data.get('statistics', {})
                        volumes_data = autocad_data.get('volumes', {})
                        material_quantities = autocad_data.get('material_quantities', {})
                        elements_data = autocad_data.get('elements', {})
                        
                        # Full data with all raw autocad extraction info
                        full_data = {
                            'extraction_time': timestamp,
                            'extraction_type': 'comprehensive_report',
                            'building_name': autocad_data.get('name', 'unnamed'),
                            'entity_count': statistics_data.get('total_entities', 0),
                            'bounds': bounds_data,
                            'layers': layers_data,
                            'statistics': statistics_data,
                            'volumes': volumes_data,
                            'material_quantities': material_quantities,
                            'elements': elements_data,
                            'bounds_valid': autocad_data.get('bounds_valid', False),
                            'volumes_calculated': autocad_data.get('volumes_calculated', False),
                            'raw_autocad_data': autocad_data
                        }
                        
                        entities_file = extraction_dir / "entities.json"
                        logging.info(f"[EXTRACTION] Writing entities.json...")
                        with open(entities_file, 'w', encoding='utf-8') as f:
                            json.dump(full_data, f, indent=2, ensure_ascii=False, default=str)
                        
                        # Summary file (lighter version without full raw data)
                        summary_data = {
                            'extraction_time': timestamp,
                            'extraction_type': 'comprehensive_report',
                            'building_name': autocad_data.get('name', 'unnamed'),
                            'entity_count': statistics_data.get('total_entities', 0),
                            'bounds': bounds_data,
                            'layers': layers_data,
                            'statistics': statistics_data,
                            'volumes': volumes_data,
                            'material_quantities': material_quantities,
                            'bounds_valid': autocad_data.get('bounds_valid', False),
                            'volumes_calculated': autocad_data.get('volumes_calculated', False)
                        }
                        
                        summary_file = extraction_dir / "summary.json"
                        logging.info(f"[EXTRACTION] Writing summary.json...")
                        with open(summary_file, 'w', encoding='utf-8') as f:
                            json.dump(summary_data, f, indent=2, ensure_ascii=False, default=str)
                        
                        logging.info(f"[EXTRACTION] Saved {statistics_data.get('total_entities', 0)} entities to {extraction_dir}")
                        return str(extraction_dir)
                        
                    except Exception as e:
                        import traceback
                        logging.error(f"[EXTRACTION] Failed to save: {e}")
                        logging.error(f"[EXTRACTION] Traceback: {traceback.format_exc()}")
                        return None
                
                # Extract building data from AutoCAD - ALWAYS CREATE FRESH EXTRACTION
                if arguments.get('use_autocad_data', True) and autocad.connected:
                    
                    # STEP 1: Extract data and save to extraction_{timestamp} folder
                    logging.info("Extracting fresh building data from AutoCAD...")
                    autocad_data = autocad.extract_building_data()
                    
                    # Check for extraction errors BEFORE trying to save
                    if not autocad_data:
                        return [types.TextContent(type="text", 
                            text="[ERROR] extract_building_data() returned empty data")]
                    
                    if 'error' in autocad_data:
                        error_msg = autocad_data.get('error', 'Unknown error')
                        return [types.TextContent(type="text", 
                            text=f"[ERROR] Extraction failed: {error_msg}")]
                    
                    saved_dir = save_building_data_to_extraction(autocad_data)
                    
                    if not saved_dir:
                        # Try to get more details about the error
                        logging.error("[EXTRACTION] Failed to save extraction data")
                        return [types.TextContent(type="text", 
                            text=f"[ERROR] Failed to save extraction data to disk. Check server logs for details. autocad_data keys: {list(autocad_data.keys()) if autocad_data else 'None'}")]
                    
                    logging.info(f"[EXTRACTION] Saved to {saved_dir}")
                    
                    # STEP 2: Read data back from extraction folder for report
                    extraction_path = Path(saved_dir)
                    autocad_data = read_extraction_data(extraction_path)
                    
                    if not autocad_data:
                        logging.error("[EXTRACTION] Failed to read extraction data")
                        return [types.TextContent(type="text", 
                            text="[ERROR] Failed to read extraction data from disk")]
                    
                    logging.info("[OK] Using data from extraction folder for report generation")
                    
                    # VALIDATION - NO FAKE DATA!
                    if not autocad_data or 'error' in autocad_data:
                        error_msg = autocad_data.get('error', 'Unknown error')
                        return [types.TextContent(type="text", 
                            text=f"[ERROR] Failed to extract building data: {error_msg}")]
                    
                    if not autocad_data.get('statistics'):
                        return [types.TextContent(type="text", 
                            text="[ERROR] No AutoCAD data found. The model appears empty.")]
                    
                    stats = autocad_data.get('statistics', {})
                    if stats.get('total_entities', 0) == 0:
                        return [types.TextContent(type="text",
                            text="[ERROR] No entities found in AutoCAD model. Create a building first.")]
                    
                    if not autocad_data.get('bounds_valid', False):
                        return [types.TextContent(type="text",
                            text="[ERROR] Could not calculate building bounds. Model geometry may be invalid.")]
                    
                    bounds = autocad_data.get('bounds', {})
                    
                    # NO MORE default values - fail if missing
                    real_width = bounds.get('width')
                    real_length = bounds.get('length')
                    real_height = bounds.get('height')
                    
                    if not all([real_width, real_length, real_height]):
                        return [types.TextContent(type="text",
                            text=f"[ERROR] Missing building dimensions. "
                                 f"width={real_width}, length={real_length}, height={real_height}. "
                                 "Check AutoCAD model.")]
                    
                    if real_width <= 0 or real_length <= 0 or real_height <= 0:
                        return [types.TextContent(type="text",
                            text=f"[ERROR] Invalid dimensions: {real_width:.2f}m x {real_length:.2f}m x {real_height:.2f}m. "
                                 "All dimensions must be positive.")]
                    
                    if real_width < 5 or real_length < 5 or real_height < 2:
                        return [types.TextContent(type="text",
                            text=f"[ERROR] Dimensions too small: {real_width:.2f}m x {real_length:.2f}m x {real_height:.2f}m. "
                                 "Check model units and scale.")]
                    
                    if not autocad_data.get('volumes_calculated', False):
                        return [types.TextContent(type="text",
                            text="[ERROR] Volume calculations failed. Check extract_building_data() function.")]
                    
                    volumes = autocad_data.get('volumes', {})
                    total_volume = volumes.get('total_volume', 0)
                    
                    if total_volume <= 0:
                        return [types.TextContent(type="text",
                            text="[ERROR] Total volume is zero or negative. No structural elements found or volume calculation failed.")]
                    
                    if 'material_quantities' not in autocad_data:
                        return [types.TextContent(type="text",
                            text="[ERROR] Material quantities not calculated. Update extract_building_data() function.")]
                    
                    material_quantities = autocad_data.get('material_quantities', {})
                    concrete_volume = material_quantities.get('concrete_volume_m3', 0)
                    
                    if concrete_volume <= 0:
                        return [types.TextContent(type="text",
                            text="[ERROR] Concrete volume is zero. Cannot generate construction schedule without material quantities.")]
                    
                    # ALL VALIDATIONS PASSED - Use REAL data
                    real_floors = max(1, int(real_height / 4.0))
                    
                    layers = autocad_data.get('layers', {})
                    wall_layer = layers.get('A-WALL', {})
                    wall_faces = wall_layer.get('AcDb3dFace', 0)
                    
                    floor_layer = layers.get('A-FLOR', {})
                    floor_faces = floor_layer.get('AcDb3dFace', 0)
                    
                    building_data = {
                        'name': autocad_data.get('name', 'AutoCAD_Building'),
                        'floors': real_floors,
                        'area': real_width * real_length,
                        'floor_area': real_width * real_length,
                        'length': real_length,
                        'width': real_width,
                        'height': real_height,
                        'floor_height': 4.0,
                        'structural_system': 'shear_wall',
                        'total_walls': wall_faces,
                        'wall_count': wall_faces,
                        'walls_per_floor': wall_faces // max(1, real_floors),
                        'total_slabs': floor_faces,
                        'floor_thickness': autocad.current_building_data.get('floor_thickness', 0.2),
                        'wall_thickness': autocad.current_building_data.get('wall_thickness', 0.3),
                        'concrete_volume_m3': concrete_volume,
                        'wall_volume_m3': volumes.get('wall_volume', 0),
                        'slab_volume_m3': volumes.get('slab_volume', 0),
                        'formwork_area_m2': material_quantities.get('formwork_area_m2', 0),
                        'rebar_tons': material_quantities.get('rebar_tons', 0),
                        'complexity': 0.5,
                        'crew_size': 20,
                        'equipment_units': 5,
                        '_autocad_raw': {
                            'total_entities': stats.get('total_entities', 0),
                            'total_3dfaces': stats.get('total_3dfaces', 0),
                            'bounds': bounds,
                            'layers': layers,
                            'volumes': volumes,
                            'material_quantities': material_quantities
                        }
                    }
                    
                    logging.info(f"Building data from REAL AutoCAD geometry:")
                    logging.info(f"   - Name: {building_data['name']}")
                    logging.info(f"   - Floors: {real_floors} (height {real_height:.1f}m / 4m)")
                    logging.info(f"   - Dimensions: {real_width:.1f}m x {real_length:.1f}m x {real_height:.1f}m")
                    logging.info(f"   - Area: {building_data['area']:.1f} mÂ²")
                    logging.info(f"   - Concrete: {concrete_volume:.2f} mÂ³")
                    logging.info(f"   - Walls: {wall_faces} faces from A-WALL layer")
                    logging.info(f"   - Slabs: {floor_faces} faces from A-FLOR layer")
                    logging.info(f"   - Formwork: {material_quantities.get('formwork_area_m2', 0):.1f} mÂ²")
                    logging.info(f"   - Rebar: {material_quantities.get('rebar_tons', 0):.2f} tons")
                else:
                    building_data = autocad.current_building_data
                    if not building_data:
                        return [types.TextContent(type="text",
                            text="[ERROR] No building data available. Create a building first or enable use_autocad_data.")]
                    
                    required_fields = ['name', 'floors', 'area', 'concrete_volume_m3']
                    missing = [f for f in required_fields if f not in building_data]
                    if missing:
                        return [types.TextContent(type="text",
                            text=f"[ERROR] Stored building data is incomplete. Missing: {', '.join(missing)}")]
                
                
                # Initialize comprehensive report generator
                logging.info("Initializing comprehensive report generator...")
                report_generator_comprehensive = ComprehensiveConstructionReportGenerator(log_dir="./logs")
                
                # Check if AI modules should be used
                use_ai_modules = arguments.get('use_ai_modules', False)
                if use_ai_modules and CONSTRUCTION_AI_AVAILABLE:
                    logging.info("AI modules ENABLED by user request")
                else:
                    logging.info("AI modules DISABLED (default behavior)")
                
                # Generate comprehensive report
                import os
                server_dir = os.path.dirname(os.path.abspath(__file__))
                output_dir = os.path.join(server_dir, 'construction_reports')
                os.makedirs(output_dir, exist_ok=True)
                logging.info(f"Generating comprehensive report to {output_dir}...")
                
                report_path = await report_generator_comprehensive.generate_comprehensive_report(
                    building_data=building_data,
                    autocad_data=autocad_data if arguments.get('use_autocad_data', True) else None,
                    output_base_dir=output_dir
                )
                
                # Create proper JSON response
                response_data = {
                    "status": "SUCCESS",
                    "report_directory": str(report_path),
                    "timestamp": datetime.now().isoformat(),
                    "generated_files": {
                        "csv_data": [
                            "construction_schedule.csv",
                            "validation_issues.csv",
                            "project_summary.csv"
                        ],
                        "visualizations": [
                            "gantt_chart.png",
                            "validation_results.png",
                            "resource_histogram.png",
                            "performance_metrics.png",
                            "module_usage_timeline.png"
                        ],
                        "reports": [
                            "CONSTRUCTION_REPORT.md",
                            "performance_log.json",
                            "module_usage_log.json"
                        ]
                    },
                    "standards_referenced": [
                        "ACI 318-19 (Concrete Design)",
                        "ACI 347-04 (Formwork Design)",
                        "Productivity Standards (Field Data)",
                        "RSMeans 2024 (Construction Costs)",
                        "ASCE 7-22 (Load Combinations)"
                    ]
                }
                
                # Only add AI modules info if they were actually used
                if use_ai_modules and CONSTRUCTION_AI_AVAILABLE:
                    response_data["ai_modules_used"] = {
                        "AIConstructionSequencer": {"status": "OK", "type": "CPM"},
                        "AIConstructionValidator": {"status": "OK"},
                        "ConstructionPatternLearner": {"status": "OK"},
                        "ConstructionAILogger": {"status": "OK", "type": "SQLite"}
                    }
                else:
                    response_data["ai_modules_used"] = "Not used (default behavior. Enable with use_ai_modules=true)"
                
                # Return as JSON string
                return [types.TextContent(type="text", 
                    text=json.dumps(response_data, indent=2))]
            
            except Exception as e:
                logging.error(f"Error generating comprehensive report: {e}", exc_info=True)
                error_response = {
                    "status": "ERROR",
                    "error": str(e),
                    "message": f"Failed to generate comprehensive report: {str(e)}",
                    "details": "Check logs for more information"
                }
                return [types.TextContent(type="text",
                    text=json.dumps(error_response, indent=2))]
        
        # Visualization and Report Tools (Legacy/Old)
        elif name == "extract_building_data" and OLD_VISUALIZATION_AVAILABLE:
            if not autocad.connected:
                return [types.TextContent(type="text", text="[ERROR] Not connected to AutoCAD")]
            
            data = autocad.extract_building_data()
            return [types.TextContent(type="text", text=json.dumps(data, indent=2))]
        
        elif name == "analyze_construction_real" and OLD_VISUALIZATION_AVAILABLE:
            if arguments.get('use_autocad_data', True) and autocad.connected:
                # Extract ACTUAL model data from AutoCAD
                autocad_data = autocad.extract_building_data()
                
                if not autocad_data or not autocad_data.get('statistics'):
                    return [types.TextContent(type="text", 
                        text="[ERROR] No AutoCAD data found. The model appears empty.")]
                
                # Use ACTUAL AutoCAD data, not formulas
                analysis = construction_analyzer.analyze_building_from_autocad(autocad_data)
                
                # Enrich building_data with calculated values for report generator
                if 'real_dimensions' in analysis:
                    dims = analysis['real_dimensions']
                    autocad.current_building_data['length'] = dims.get('length_m', 0)
                    autocad.current_building_data['width'] = dims.get('width_m', 0)
                    autocad.current_building_data['height'] = dims.get('height_m', 0)
                    autocad.current_building_data['floor_area'] = dims.get('length_m', 0) * dims.get('width_m', 0)
                    
                    # Calculate floors from height
                    height = dims.get('height_m', 0)
                    autocad.current_building_data['floors'] = max(1, int(height / 4.0))
                    autocad.current_building_data['floor_height'] = 4.0
                    autocad.current_building_data['structural_system'] = 'shear_wall'
                
                if 'entity_counts' in analysis:
                    counts = analysis['entity_counts']
                    autocad.current_building_data['total_walls'] = counts.get('walls', 0)
            else:
                # Fallback to formula-based if requested
                building_data = autocad.current_building_data
                if not building_data:
                    return [types.TextContent(type="text",
                        text="[ERROR] No data available. Create a building first.")]
                analysis = construction_analyzer.analyze_building(building_data)
            
            # Store for reporting
            autocad.current_building_data['analysis'] = analysis
            
            return [types.TextContent(type="text", text=json.dumps(analysis, indent=2, default=str))]
        
        elif name == "generate_construction_report" and OLD_VISUALIZATION_AVAILABLE:
            if not autocad.current_building_data.get('analysis'):
                return [types.TextContent(type="text", 
                    text="[ERROR] No analysis available. Run analyze_construction_real first.")]
            
            building_data = autocad.current_building_data
            analysis = building_data.get('analysis', {})
            
            # Generate professional PDF report
            report_path = report_generator.generate_full_report(
                building_data,
                analysis,
                include_gantt=arguments.get('include_gantt', True)
            )
            
            return [types.TextContent(type="text", 
                text=f"[SUCCESS] Professional report generated:\n{report_path}\n\n" +
                     f"Also created:\n- Excel file with all data\n- JSON data file\n" +
                     f"Location: {report_generator.output_dir}")]
        
        # ============ NEW MODULE TOOL HANDLERS ============
        elif name == "extract_all_entities_structured" and NEW_MODULES_AVAILABLE:
            if not autocad.connected:
                return [types.TextContent(type="text", 
                    text=response_formatter.format_autocad_not_connected())]
            
            extraction_result = entity_extractor.extract_all_entities(
                autocad,
                arguments
            )
            
            if 'success' not in extraction_result or not extraction_result['success']:
                error_msg = extraction_result['error'] if 'error' in extraction_result else 'Unknown error'
                return [types.TextContent(type="text",
                    text=response_formatter.format_error(1002, custom_message=error_msg))]
            
            entities = extraction_result['entities'] if 'entities' in extraction_result else []
            
            summary = save_extraction_to_file(entities, extraction_result, "all_entities", autocad)
            
            return [types.TextContent(type="text", text=json.dumps(summary, indent=2))]
        
        elif name == "extract_by_layer_structured" and NEW_MODULES_AVAILABLE:
            if not autocad.connected:
                return [types.TextContent(type="text",
                    text=response_formatter.format_autocad_not_connected())]
            
            layer_name = arguments['layer_name'] if 'layer_name' in arguments else None
            result = entity_extractor.extract_by_layer(autocad, layer_name, arguments)
            
            if 'success' not in result or not result['success']:
                return [types.TextContent(type="text",
                    text=response_formatter.format_invalid_layer(layer_name))]
            
            entities = result['entities'] if 'entities' in result else []
            
            summary = save_extraction_to_file(entities, result, f"layer_{layer_name}", autocad)
            
            return [types.TextContent(type="text", text=json.dumps(summary, indent=2))]
        
        
        elif name == "get_building_metadata" and NEW_MODULES_AVAILABLE:
            if not autocad.connected:
                return [types.TextContent(type="text",
                    text=response_formatter.format_autocad_not_connected())]
            
            bounds = entity_extractor._get_model_bounds(autocad)
            unit_info = entity_extractor._detect_unit_system(autocad)
            coord_system = coordinate_transformer.get_coordinate_system(autocad.doc)
            
            data = {
                'bounds': bounds,
                'unit_system': unit_info,
                'coordinate_system': coord_system
            }
            
            response = response_formatter.format_success(
                data=data,
                unit_system=unit_info.get('system', 'metric'),
                coordinate_system=coord_system,
                summary=f"Building bounds: {bounds.get('width', 0):.1f} x {bounds.get('length', 0):.1f} x {bounds.get('height', 0):.1f} {unit_info.get('length_unit', 'm')}"
            )
            
            return [types.TextContent(type="text", text=response)]
        
        elif name == "query_standard" and NEW_MODULES_AVAILABLE:
            standard = arguments.get('standard')
            query_type = arguments.get('query_type')
            params = arguments.get('parameters', {})
            
            result = None
            
            if query_type == 'material':
                grade = params.get('grade')
                result = standards_manager.get_material(standard, grade)
            elif query_type == 'load':
                design_method = params.get('design_method', 'LRFD')
                result = standards_manager.get_load_combinations(standard, design_method)
            elif query_type == 'mapping':
                layer = params.get('layer_name')
                result = standards_manager.map_layer_to_ifc4(layer)
            elif query_type == 'info':
                result = standards_manager.get_standard_info(standard)
            
            response = response_formatter.format_standards_query(
                standard=standard,
                query_type=query_type,
                result=result
            )
            
            return [types.TextContent(type="text", text=response)]
        
        elif name == "get_load_combinations" and NEW_MODULES_AVAILABLE:
            standard = arguments.get('standard', 'ASCE_7_22')
            design_method = arguments.get('design_method', 'LRFD')
            
            combos = standards_manager.get_load_combinations(standard, design_method)
            
            response = response_formatter.format_standards_query(
                standard=standard,
                query_type='load_combinations',
                result=combos
            )
            
            return [types.TextContent(type="text", text=response)]
        
        elif name == "map_to_ifc4" and NEW_MODULES_AVAILABLE:
            layer_name = arguments.get('layer_name')
            
            mapping = standards_manager.map_layer_to_ifc4(layer_name)
            
            if not mapping:
                return [types.TextContent(type="text",
                    text=response_formatter.format_error(3001,
                        custom_message=f"No IFC4 mapping found for layer: {layer_name}"))]
            
            response = response_formatter.format_standards_query(
                standard='IFC4',
                query_type='layer_mapping',
                result=mapping
            )
            
            return [types.TextContent(type="text", text=response)]
        
        elif name == "get_construction_sequence_standard" and NEW_MODULES_AVAILABLE:
            building_type = arguments.get('building_type')
            standard = arguments.get('standard', 'RSMeans_2024')
            
            sequence = standards_manager.get_construction_sequence(building_type, standard)
            
            if not sequence:
                return [types.TextContent(type="text",
                    text=response_formatter.format_error(3001,
                        custom_message=f"No sequence found for building type: {building_type}"))]
            
            response = response_formatter.format_standards_query(
                standard=standard,
                query_type='construction_sequence',
                result=sequence
            )
            
            return [types.TextContent(type="text", text=response)]
        
        elif name == "validate_for_export" and NEW_MODULES_AVAILABLE:
            if not autocad.connected:
                return [types.TextContent(type="text",
                    text=response_formatter.format_autocad_not_connected())]
            
            target_format = arguments.get('target_format')
            
            # Extract building data first
            extraction_result = entity_extractor.extract_all_entities(autocad, {})
            
            # Validate
            validation_result = geometry_validator.validate_for_export(
                extraction_result,
                target_format
            )
            
            response = response_formatter.format_validation_result(
                validation_data=validation_result,
                passed=validation_result.get('passed', False)
            )
            
            return [types.TextContent(type="text", text=response)]
        
        elif name == "check_geometry_quality" and NEW_MODULES_AVAILABLE:
            if not autocad.connected:
                return [types.TextContent(type="text",
                    text=response_formatter.format_autocad_not_connected())]
            
            # Extract entities
            extraction_result = entity_extractor.extract_all_entities(autocad, {})
            entities = extraction_result.get('entities', [])
            
            # Validate connectivity
            validation_result = geometry_validator.validate_connectivity(entities)
            
            response = response_formatter.format_validation_result(
                validation_data=validation_result,
                passed=validation_result.get('passed', False)
            )
            
            return [types.TextContent(type="text", text=response)]
        
        elif name == "convert_units" and NEW_MODULES_AVAILABLE:
            value = arguments.get('value')
            from_unit = arguments.get('from_unit')
            to_unit = arguments.get('to_unit')
            unit_type = arguments.get('unit_type', 'length')
            
            try:
                result = unit_converter.convert(value, from_unit, to_unit, unit_type)
                
                data = {
                    'original_value': value,
                    'original_unit': from_unit,
                    'converted_value': result,
                    'converted_unit': to_unit,
                    'unit_type': unit_type
                }
                
                response = response_formatter.format_success(
                    data=data,
                    summary=f"{value} {from_unit} = {result:.4f} {to_unit}"
                )
                
                return [types.TextContent(type="text", text=response)]
            except Exception as e:
                return [types.TextContent(type="text",
                    text=response_formatter.format_error(2002,
                        custom_message=str(e)))]
        
        elif name == "get_coordinate_system" and NEW_MODULES_AVAILABLE:
            if not autocad.connected:
                return [types.TextContent(type="text",
                    text=response_formatter.format_autocad_not_connected())]
            
            coord_system = coordinate_transformer.get_coordinate_system(autocad.doc)
            
            data = {
                'coordinate_system': coord_system,
                'description': 'World Coordinate System' if coord_system == 'WCS' else 'User Coordinate System'
            }
            
            response = response_formatter.format_success(
                data=data,
                coordinate_system=coord_system,
                summary=f"Current coordinate system: {coord_system}"
            )
            
            return [types.TextContent(type="text", text=response)]
        
        elif name == "query_aci_318_complete" and NEW_MODULES_AVAILABLE:
            from standards_module import get_standards_manager
            
            mgr = get_standards_manager()
            query_type = arguments.get("query_type")
            
            try:
                if query_type == "phi_factor":
                    result = mgr.get_phi_factor(arguments.get("member_type", "moment"))
                    
                elif query_type == "concrete_props":
                    result = mgr.get_concrete_properties(arguments.get("fc_psi"))
                    
                elif query_type == "rebar_props":
                    result = mgr.get_rebar_properties(arguments.get("grade", "60"))
                    
                elif query_type == "development_length":
                    result = mgr.get_development_length(
                        arguments.get("bar_size", "#8"),
                        arguments.get("fc_psi", 4000),
                        arguments.get("fy_psi", 60000)
                    )
                    
                elif query_type == "beam_shear":
                    result = mgr.get_beam_shear_capacity(
                        arguments.get("bw", 12),
                        arguments.get("d", 20),
                        arguments.get("fc_psi", 4000)
                    )
                else:
                    result = {"error": f"Unknown query_type: {query_type}"}
                
                return [types.TextContent(
                    type="text", 
                    text=json.dumps(result, indent=2)
                )]
                
            except Exception as e:
                return [types.TextContent(
                    type="text",
                    text=f"[ERROR] ACI 318 query failed: {str(e)}"
                )]

        elif name == "query_formwork" and NEW_MODULES_AVAILABLE:
            from standards_module import get_standards_manager
            
            mgr = get_standards_manager()
            query_type = arguments.get("query_type")
            
            try:
                if query_type == "loads":
                    result = mgr.get_formwork_loads(
                        arguments.get("use_motorized_carts", False)
                    )
                    
                elif query_type == "lateral_pressure":
                    result = mgr.get_lateral_pressure(
                        arguments.get("placement_rate", 2.0),
                        arguments.get("temperature", 70),
                        arguments.get("concrete_height", 10)
                    )
                    
                elif query_type == "removal_time":
                    result = mgr.get_formwork_removal_time(
                        arguments.get("member_type", "slab"),
                        arguments.get("temperature", 70)
                    )
                else:
                    result = {"error": f"Unknown query_type: {query_type}"}
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
                
            except Exception as e:
                return [types.TextContent(
                    type="text",
                    text=f"[ERROR] Formwork query failed: {str(e)}"
                )]

        elif name == "query_productivity" and NEW_MODULES_AVAILABLE:
            from standards_module import get_standards_manager
            
            mgr = get_standards_manager()
            query_type = arguments.get("query_type")
            
            try:
                if query_type == "get_rate":
                    result = mgr.get_productivity_rate(
                        arguments.get("category", "concrete"),
                        arguments.get("task", "manual_laying")
                    )
                    
                elif query_type == "calculate_duration":
                    result = mgr.calculate_labor_duration(
                        arguments.get("task"),
                        arguments.get("quantity"),
                        arguments.get("crew_size", 6)
                    )
                    
                elif query_type == "estimate_slab":
                    result = mgr.estimate_concrete_slab_construction(
                        arguments.get("area_m2"),
                        arguments.get("thickness_mm"),
                        arguments.get("crew_size", 6)
                    )
                    
                elif query_type == "list_categories":
                    result = {"categories": mgr.list_productivity_categories()}
                    
                elif query_type == "list_tasks":
                    result = {"tasks": mgr.list_category_tasks(
                        arguments.get("category", "concrete")
                    )}
                else:
                    result = {"error": f"Unknown query_type: {query_type}"}
                
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
                
            except Exception as e:
                return [types.TextContent(
                    type="text",
                    text=f"[ERROR] Productivity query failed: {str(e)}"
                )]
        
        else:
            return [types.TextContent(
                type="text",
                text=f"[ERROR] Unknown tool: {name}"
            )]
            
    except Exception as e:
        logging.error(f"Error in {name}: {e}", exc_info=True)
        return [types.TextContent(
            type="text",
            text=f"[ERROR] Error: {str(e)}"
        )]

async def main():
    logging.info("Starting AutoCAD 2024 MCP Server...")
    
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="autocad-2024",
                server_version="1.0.0",
                capabilities={}
            )
        )

if __name__ == "__main__":
    asyncio.run(main())
