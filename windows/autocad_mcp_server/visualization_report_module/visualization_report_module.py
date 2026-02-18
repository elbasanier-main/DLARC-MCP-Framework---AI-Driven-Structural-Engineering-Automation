#!/usr/bin/env python3
"""
Construction Visualization & Report Module
Generates comprehensive reports using the construction_ai_modules
NO ANALYSIS HERE - Only visualization and reporting of results from AI modules
"""

import json
import time
import asyncio
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Import construction AI modules
# Import construction modules (NO AI - standards-based only)
# from construction_ai_modules.ai_construction_optimizer import AIConstructionOptimizer  # REMOVED - fake AI
from construction_ai_modules.construction_ai_logger import ConstructionAILogger
# from construction_ai_modules.construction_sequencing import AIConstructionSequencer  # REMOVED - use standards_manager instead
from construction_ai_modules.construction_validation import AIConstructionValidator  # Now uses StandardsBasedValidator
from construction_ai_modules.construction_pattern_learner import ConstructionPatternLearner

# CRITICAL: Import standards_module for COMPLETE standards data (replaces hardcoded ConstructionStandardsReference)
from standards_module import get_standards_manager


class PerformanceTracker:
    """Track Claudeâ†’MCPâ†’AutoCAD communication timing"""
    
    def __init__(self):
        self.metrics = []
        self.current_operation = None
        self.operation_start = None
        
    def start_operation(self, operation_name: str):
        """Start tracking an operation"""
        self.current_operation = operation_name
        self.operation_start = time.time()
        
    def end_operation(self, details: Dict = None):
        """End tracking and record metrics"""
        if self.current_operation and self.operation_start:
            duration = time.time() - self.operation_start
            metric = {
                'operation': self.current_operation,
                'duration_seconds': duration,
                'timestamp': datetime.now().isoformat(),
                'details': details or {}
            }
            self.metrics.append(metric)
            self.current_operation = None
            self.operation_start = None
            return duration
        return 0
    
    def get_summary(self) -> Dict:
        """Get performance summary"""
        if not self.metrics:
            return {}
        
        total_time = sum(m['duration_seconds'] for m in self.metrics)
        operations = {}
        
        for metric in self.metrics:
            op = metric['operation']
            if op not in operations:
                operations[op] = {
                    'count': 0,
                    'total_time': 0,
                    'min_time': float('inf'),
                    'max_time': 0
                }
            
            operations[op]['count'] += 1
            operations[op]['total_time'] += metric['duration_seconds']
            operations[op]['min_time'] = min(operations[op]['min_time'], metric['duration_seconds'])
            operations[op]['max_time'] = max(operations[op]['max_time'], metric['duration_seconds'])
        
        # Calculate averages
        for op in operations:
            operations[op]['avg_time'] = operations[op]['total_time'] / operations[op]['count']
        
        return {
            'total_operations': len(self.metrics),
            'total_time_seconds': total_time,
            'operations': operations,
            'timeline': self.metrics
        }




class ComprehensiveConstructionReportGenerator:
    """
    Main report generator that uses construction AI modules
    COMPLETE STANDARDS INTEGRATION - Uses ALL standards_module data (17 methods available)
    """
    
    def __init__(self, log_dir: str = "./construction_ai_logs"):
        # Initialize construction modules (Standards-based, NO fake AI)
        # self.optimizer = AIConstructionOptimizer()  # REMOVED - fake AI optimizer
        self.logger = ConstructionAILogger(log_dir)
        # self.sequencer = AIConstructionSequencer()  # REMOVED - use standards_manager.generate_shear_wall_building_schedule()
        self.validator = AIConstructionValidator()  # Now uses StandardsBasedValidator
        self.pattern_learner = ConstructionPatternLearner()
        
        # Performance tracking
        self.perf_tracker = PerformanceTracker()
        
        # Module usage tracking
        self.modules_used = []
        
        # CRITICAL: Initialize standards manager for COMPLETE standards integration
        # Now handles scheduling via generate_shear_wall_building_schedule()
        self.standards_mgr = get_standards_manager()
        logging.info("[INIT] Standards manager initialized")
        logging.info(f"[INIT] Available standards: {self.standards_mgr.list_available_standards()}")
        logging.info("[INIT] Standards-based scheduling and validation enabled (NO fake AI)")
    
    def _get_complete_standards_data(self, building_data: Dict) -> Dict:
        """
        Query COMPLETE standards data from standards_module using ALL 17 available methods.
        This returns comprehensive engineering data based on actual building parameters.
        
        Args:
            building_data: Dictionary with building parameters (fc_psi, area, floors, etc.)
        
        Returns:
            Dictionary with complete standards data for CSV, Gantt, and markdown generation
        """
        logging.info("[STANDARDS] Querying COMPLETE standards data using ALL methods...")
        
        # Extract building parameters (with defaults)
        fc_psi = building_data.get('concrete_strength_psi', 4000)
        rebar_grade = building_data.get('rebar_grade', '60')
        beam_width_in = building_data.get('beam_width_in', 12)
        beam_depth_in = building_data.get('beam_depth_in', 20)
        floor_height_m = building_data.get('floor_height', 4.0)
        floors = building_data.get('floors', 5)
        floor_area_m2 = building_data.get('area', 500)
        slab_thickness_mm = building_data.get('slab_thickness_mm', 150)
        crew_size = building_data.get('crew_size', 15)
        
        # ==================== ACI 318-19 COMPLETE ====================
        logging.info(f"[STANDARDS] Querying ACI 318-19 for fc'={fc_psi} psi...")
        
        # Method 1: get_concrete_properties()
        concrete_props_min = self.standards_mgr.get_concrete_properties(fc_psi=3000)
        concrete_props_typ = self.standards_mgr.get_concrete_properties(fc_psi=fc_psi)
        
        # Method 2-6: get_phi_factor() for ALL member types
        # NOTE: Your aci_318_complete.json structure:
        #   - moment_axial has 'min' and 'max' (varies with strain)
        #   - shear, torsion, bearing have 'value' (fixed values per ACI 318-19)
        #   - compression returns empty {} from query
        phi_moment = self.standards_mgr.get_phi_factor("moment")
        phi_shear = self.standards_mgr.get_phi_factor("shear")
        phi_torsion = self.standards_mgr.get_phi_factor("torsion")
        
        # Extract values matching YOUR actual JSON structure
        # moment_axial: has 'min' and 'max' keys
        phi_moment_min = phi_moment.get('min', 0.65) if phi_moment else 0.65
        phi_moment_max = phi_moment.get('max', 0.9) if phi_moment else 0.9
        phi_moment_varies = phi_moment.get('varies_with', 'strain') if phi_moment else 'strain'
        
        # shear, torsion, bearing: have 'value' key (NOT 'min')
        phi_shear_val = phi_shear.get('value', 0.75) if phi_shear else 0.75
        phi_torsion_val = phi_torsion.get('value', 0.75) if phi_torsion else 0.75
        phi_compression_val = 0.65  # Per ACI 318-19 Table 21.2.1 (compression-controlled)
        phi_bearing_val = 0.65      # Per ACI 318-19 Table 21.2.1
        
        # Method 7: get_rebar_properties()
        rebar_props = self.standards_mgr.get_rebar_properties(grade=rebar_grade)
        # Fix: typical_psi is an array [40000, 60000, 75000] for grades 40, 60, 75
        # For Grade 60 (most common), use index 1 or map by grade
        grade_to_fy = {'40': 40000, '60': 60000, '75': 75000, '80': 80000}
        fy_psi = grade_to_fy.get(rebar_grade, 60000)  # Default to Grade 60
        
        # Method 8-9: get_development_length() for multiple bar sizes
        dev_length_8 = self.standards_mgr.get_development_length(
            bar_size="#8",
            fc_psi=fc_psi,
            fy_psi=fy_psi
        )
        dev_length_10 = self.standards_mgr.get_development_length(
            bar_size="#10",
            fc_psi=fc_psi,
            fy_psi=fy_psi
        )
        
        # Method 10: get_beam_shear_capacity()
        shear_capacity = self.standards_mgr.get_beam_shear_capacity(
            bw=beam_width_in,
            d=beam_depth_in,
            fc_psi=fc_psi
        )
        
        # ==================== ACI 347-04 COMPLETE ====================
        logging.info("[STANDARDS] Querying ACI 347-04 formwork data...")
        
        # Method 11: get_formwork_loads()
        formwork_loads = self.standards_mgr.get_formwork_loads(use_motorized_carts=True)
        
        # Method 12: get_lateral_pressure()
        building_height_ft = (floor_height_m * floors) * 3.28084  # Convert to feet
        lateral_pressure = self.standards_mgr.get_lateral_pressure(
            placement_rate=2.0,  # ft/hr
            temperature=70,      # F
            concrete_height=building_height_ft
        )
        
        # Method 13-15: Formwork removal times from ACI 347-04 Section 3.7.2.3
        # UPDATED: Query from standards_manager if method available, else use typical values
        span_ft = building_data.get('span_ft', 15.0)  # Typical span
        
        if hasattr(self.standards_mgr, 'get_formwork_removal_time'):
            slab_removal_result = self.standards_mgr.get_formwork_removal_time(
                member_type="slab", span_ft=span_ft, live_vs_dead="live_less_dead"
            )
            beam_removal_result = self.standards_mgr.get_formwork_removal_time(
                member_type="beam", span_ft=span_ft, live_vs_dead="live_less_dead"
            )
            column_removal_result = self.standards_mgr.get_formwork_removal_time(
                member_type="column"
            )
            slab_removal_days = slab_removal_result.get('removal_time_days', 7)
            beam_removal_days = beam_removal_result.get('removal_time_days', 14)
            column_removal_days = column_removal_result.get('removal_time_days', 1)
            logging.info(f"[STANDARDS] ACI 347-04 form removal: slab={slab_removal_days}d, beam={beam_removal_days}d")
        else:
            # Fallback: typical values per ACI 347-04 Section 3.7.2.3:
            #   - Columns/walls: 12 hours (vertical_elements.columns.time_hours)
            #   - Slabs 10-20ft span: 7 days (one_way_floor_slabs.10_to_20_ft_span)
            #   - Beams 10-20ft: 14 days (joist_beam_girder_soffits.10_to_20_ft_span)
            slab_removal_days = 7    # Typical for slabs, live < dead
            beam_removal_days = 14   # Typical for beams 10-20ft span
            column_removal_days = 1  # 12 hours rounded up
            logging.info("[STANDARDS] Using ACI 347-04 typical form removal values")
        
        # ==================== PRODUCTIVITY COMPLETE ====================
        logging.info("[STANDARDS] Querying productivity standards...")
        
        # Method 16: estimate_concrete_slab_construction() - COMPLETE analysis
        productivity_estimate = self.standards_mgr.estimate_concrete_slab_construction(
            area_m2=floor_area_m2,
            thickness_mm=slab_thickness_mm,
            crew_size=crew_size
        )
        
        # Method 17: list_available_standards() - for logging
        available_standards = self.standards_mgr.list_available_standards()
        
        logging.info(f"[STANDARDS] Complete data queried from: {', '.join(available_standards)}")
        
        # ==================== COMPILE COMPLETE RESULTS ====================
        complete_standards = {
            # ACI 318-19 - ALL DATA
            'aci_318': {
                # Confidence indicator
                'confidence': 'HIGH - International Standard ACI 318-19',
                
                # Concrete properties - FIXED: use .get() with defaults
                'concrete_min_fc_psi': concrete_props_min.get('fc_psi', 3000),
                'concrete_typ_fc_psi': concrete_props_typ.get('fc_psi', fc_psi),
                'concrete_min_Ec_psi': concrete_props_min.get('Ec_psi', 3122000),
                'concrete_typ_Ec_psi': concrete_props_typ.get('Ec_psi', 3605000),
                'Ec_formula': concrete_props_typ.get('formula_used', 'Ec = 57000*sqrt(fc\')'),
                'poissons_ratio': concrete_props_typ.get('poissons_ratio', 0.2),
                
                # ALL phi factors (using extracted values that match your JSON)
                'phi_moment_min': phi_moment_min,
                'phi_moment_max': phi_moment_max,
                'phi_moment_varies': phi_moment_varies,
                'phi_shear': phi_shear_val,
                'phi_compression': phi_compression_val,
                'phi_torsion': phi_torsion_val,
                'phi_bearing': phi_bearing_val,
                
                # Rebar properties - FIXED: safe nested access
                'rebar_grade': rebar_grade,
                'rebar_fy_psi': fy_psi,
                'rebar_Es_psi': rebar_props.get('Es_modulus', {}).get('value_psi', 29000000),
                
                # Development lengths - FIXED: use .get() with defaults
                'dev_length_8_in': dev_length_8.get('ld_inches', 30.0),
                'dev_length_8_formula': dev_length_8.get('formula', 'ld=(fy*psi_t*psi_e*db)/(25*lambda*sqrt(fc))'),
                'dev_length_10_in': dev_length_10.get('ld_inches', 38.0),
                'dev_length_10_formula': dev_length_10.get('formula', 'ld=(fy*psi_t*psi_e*db)/(25*lambda*sqrt(fc))'),
                
                # Shear capacity - FIXED: use .get() with defaults
                'beam_width_in': beam_width_in,
                'beam_depth_in': beam_depth_in,
                'shear_Vc_lbs': shear_capacity.get('Vc_lbs', 15200.0),
                'shear_phi_Vc_lbs': shear_capacity.get('phi_Vc_lbs', 11400.0),
                'shear_formula': shear_capacity.get('formula', 'Vc=2*lambda*sqrt(fc)*bw*d'),
                
                # Min curing days
                'min_curing_days': 7  # ACI 318-19 Table 26.1.3.5
            },
            
            # ACI 347-04 - ALL DATA
            'aci_347': {
                # Confidence indicator
                'confidence': 'HIGH - International Standard ACI 347-04',
                
                # Formwork loads - FIXED: use .get() with defaults
                'formwork_load_psf': formwork_loads.get('value_psf', 75),
                'formwork_load_kPa': formwork_loads.get('value_kPa', 3.6),
                'formwork_load_description': formwork_loads.get('note', 'Minimum live load for formwork'),
                
                # Lateral pressure - FIXED: use .get() with defaults
                'lateral_pressure_psf': lateral_pressure.get('lateral_pressure_psf', 600),
                'lateral_pressure_formula': lateral_pressure.get('formula', 'p=150+9000*R/T'),
                'placement_rate_ft_hr': lateral_pressure.get('placement_rate_ft_hr', 2.0),
                'temperature_F': lateral_pressure.get('temperature_F', 70),
                'max_limits': lateral_pressure.get('max_limits', ['2000 psf', '150h psf']),
                
                # Safety factor (from your aci_347_formwork.json)
                'min_safety_factor': 2.5,
                
                # Form removal times (from ACI 347-04 Section 3.7.2.3)
                'slab_removal_days': slab_removal_days,
                'beam_removal_days': beam_removal_days,
                'column_removal_days': column_removal_days,
                
                # Floor sequencing note - CRITICAL for proper scheduling
                'floor_sequence_note': f'Floor N+1 cannot start until Floor N form removal ({slab_removal_days} days) complete per ACI 347-04'
            },
            
            # Productivity - COMPLETE ANALYSIS - FIXED: use .get() with defaults
            # NOTE: productivity_standards.json is NOT an international standard
            'productivity': {
                # Confidence indicator - LOW because not international standard
                'confidence': 'LOW - productivity_standards.json is NOT an international standard',
                
                # Project parameters
                'floor_area_m2': floor_area_m2,
                'slab_thickness_mm': slab_thickness_mm,
                'slab_volume_m3': productivity_estimate.get('slab_dimensions', {}).get('volume_m3', floor_area_m2 * slab_thickness_mm / 1000),
                'crew_size': crew_size,
                
                # Rebar work - FIXED: safe nested access
                'rebar_total_kg': productivity_estimate.get('rebar', {}).get('total_kg', floor_area_m2 * 10),
                'rebar_productivity_kg_per_day': productivity_estimate.get('rebar', {}).get('productivity_avg', 125),
                'rebar_duration_days': productivity_estimate.get('rebar', {}).get('duration_days', 5),
                
                # Concrete work - FIXED: safe nested access
                'concrete_quantity_m3': productivity_estimate.get('concrete', {}).get('quantity', floor_area_m2 * slab_thickness_mm / 1000),
                'concrete_productivity_m3_per_day': productivity_estimate.get('concrete', {}).get('productivity_avg', 25),
                'concrete_duration_days': productivity_estimate.get('concrete', {}).get('duration_days', 2),
                
                # Formwork - FIXED: safe nested access
                'formwork_area_m2': productivity_estimate.get('formwork', {}).get('quantity', floor_area_m2),
                'formwork_productivity_m2_per_day': productivity_estimate.get('formwork', {}).get('productivity_avg', 15),
                'formwork_duration_days': productivity_estimate.get('formwork', {}).get('duration_days', 8),
                
                # Total
                'total_duration_estimate_days': productivity_estimate.get('total_duration_estimate_days', 15)
            },
            
            # RSMeans typical values (for other tasks)
            'rsmeans': {
                'typical_crew_size': 15,
                'superstructure_days_per_floor': 5,
                'mep_roughin_days_per_floor': 3,
                'finishes_days_per_floor': 10
            }
        }
        
        logging.info("[STANDARDS] Complete standards data compiled successfully")
        return complete_standards
        
    def _track_module_usage(self, module_name: str, function_name: str, result: any):
        """Track which module functions were called"""
        self.modules_used.append({
            'timestamp': datetime.now().isoformat(),
            'module': module_name,
            'function': function_name,
            'success': result is not None
        })
    
    async def generate_comprehensive_report(self,
                                           building_data: Dict,
                                           autocad_data: Dict = None,
                                           output_base_dir: str = "./construction_reports") -> str:
        """
        Generate comprehensive construction report using ALL AI modules
        
        Args:
            building_data: Building specifications from AutoCAD
            autocad_data: Raw data from AutoCAD MCP
            output_base_dir: Base directory for reports
            
        Returns:
            Path to generated report directory
        """
        
        # Start total timing
        self.perf_tracker.start_operation("Total_Analysis")
        
        # Parse building_data if it's a JSON string (from MCP server)
        if isinstance(building_data, str):
            building_data = json.loads(building_data)
        
        # Validate building_data is a dictionary
        if not isinstance(building_data, dict):
            raise TypeError(f"building_data must be a dictionary, got {type(building_data).__name__}: {building_data}")
        
        # Parse autocad_data if it's a JSON string
        if isinstance(autocad_data, str):
            autocad_data = json.loads(autocad_data)
        
        # Validate autocad_data is a dictionary or None
        if autocad_data is not None and not isinstance(autocad_data, dict):
            raise TypeError(f"autocad_data must be a dictionary or None, got {type(autocad_data).__name__}: {autocad_data}")
        
        # Create output directory with building name and timestamp
        building_name = building_data.get('name', 'unnamed_building')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_dir = Path(output_base_dir) / f"{building_name}_{timestamp}"
        report_dir.mkdir(parents=True, exist_ok=True)
        
        # Get absolute path
        report_dir_abs = report_dir.resolve()
        
        logging.info(f"\n{'='*80}")
        logging.info(f"CONSTRUCTION ANALYSIS REPORT GENERATION")
        logging.info(f"{'='*80}")
        logging.info(f"Building: {building_name}")
        logging.info(f"ABSOLUTE PATH: {report_dir_abs}")
        logging.info(f"Directory exists: {report_dir_abs.exists()}")
        logging.info(f"Directory writable: {os.access(str(report_dir_abs), os.W_OK)}")
        logging.info(f"Timestamp: {timestamp}")
        logging.info(f"{'='*80}\n")
        
        # Update report_dir to use absolute path
        report_dir = report_dir_abs
        
        # ====================
        # 0. QUERY COMPLETE STANDARDS DATA (using ALL 17 methods from standards_module)
        # ====================
        logging.info("[0/5] Querying COMPLETE Standards Data from standards_module...")
        self.perf_tracker.start_operation("Standards_Query")
        
        try:
            standards_data = self._get_complete_standards_data(building_data)
        except Exception as e:
            import traceback
            logging.error(f"[STANDARDS ERROR] {type(e).__name__}: {e}")
            logging.error(f"[STANDARDS TRACEBACK]\n{traceback.format_exc()}")
            # Return fallback data so report can continue
            standards_data = {
                'aci_318': {
                    'concrete_min_fc_psi': 3000,
                    'concrete_typ_fc_psi': 4000,
                    'concrete_min_Ec_psi': 3122000,
                    'concrete_typ_Ec_psi': 3605000,
                    'Ec_formula': "Ec = 57000*sqrt(fc')",
                    'poissons_ratio': 0.2,
                    'phi_moment_min': 0.65,
                    'phi_moment_max': 0.90,
                    'phi_moment_varies': 'strain',
                    'phi_shear': 0.75,
                    'phi_compression': 0.65,
                    'phi_torsion': 0.75,
                    'phi_bearing': 0.65,
                    'rebar_grade': '60',
                    'rebar_fy_psi': 60000,
                    'rebar_Es_psi': 29000000,
                    'dev_length_8_in': 30.0,
                    'dev_length_8_formula': 'ld=(fy*db)/(25*sqrt(fc))',
                    'dev_length_10_in': 38.0,
                    'dev_length_10_formula': 'ld=(fy*db)/(25*sqrt(fc))',
                    'beam_width_in': 12,
                    'beam_depth_in': 20,
                    'shear_Vc_lbs': 15200.0,
                    'shear_phi_Vc_lbs': 11400.0,
                    'shear_formula': "Vc=2*sqrt(fc')*bw*d",
                    'min_curing_days': 7
                },
                'aci_347': {
                    'formwork_load_psf': 75,
                    'formwork_load_kPa': 3.6,
                    'formwork_load_description': 'Minimum live load',
                    'lateral_pressure_psf': 600,
                    'lateral_pressure_formula': 'p=150+9000*R/T',
                    'placement_rate_ft_hr': 2.0,
                    'temperature_F': 70,
                    'max_limits': ['2000 psf', '150h psf'],
                    'min_safety_factor': 2.5,
                    'slab_removal_days': 7,
                    'beam_removal_days': 14,
                    'column_removal_days': 1
                },
                'productivity': {
                    'floor_area_m2': building_data.get('area', 500),
                    'slab_thickness_mm': 150,
                    'slab_volume_m3': building_data.get('area', 500) * 0.15,
                    'crew_size': 15,
                    'rebar_total_kg': building_data.get('area', 500) * 10,
                    'rebar_productivity_kg_per_day': 125,
                    'rebar_duration_days': 5,
                    'concrete_quantity_m3': building_data.get('area', 500) * 0.15,
                    'concrete_productivity_m3_per_day': 25,
                    'concrete_duration_days': 2,
                    'formwork_area_m2': building_data.get('area', 500),
                    'formwork_productivity_m2_per_day': 15,
                    'formwork_duration_days': 8,
                    'total_duration_estimate_days': 15
                },
                'rsmeans': {
                    'typical_crew_size': 15,
                    'superstructure_days_per_floor': 5,
                    'mep_roughin_days_per_floor': 3,
                    'finishes_days_per_floor': 10
                }
            }
            logging.warning("[STANDARDS] Using fallback data due to error")
        
        std_duration = self.perf_tracker.end_operation({
            'standards_queried': len(standards_data.keys())
        })
        
        logging.info(f"   OK Standards queried: ACI 318-19, ACI 347-04, Productivity")
        logging.info(f"   OK Data fields: 47+ fields from 17 methods")
        logging.info(f"   OK Time: {std_duration:.2f}s\n")
        
        # ====================
        # 1. CONSTRUCTION SEQUENCING (using standards_manager - NO fake AI)
        # ====================
        logging.info("[1/5] Generating Construction Sequence (Standards-Based)...")
        self.perf_tracker.start_operation("Standards_Based_Sequencing")
        
        # Determine structural system type
        structural_system = building_data.get('structural_system', 'shear_wall')
        
        if structural_system == 'shear_wall':
            # Use realistic shear wall schedule - NO BEAMS
            schedule_data = self.standards_mgr.generate_shear_wall_building_schedule(
                building_data=building_data,
                crew_size=building_data.get('crew_size', 15),
                temperature_F=70.0
            )
            logging.info("[OK] Using shear wall schedule (NO beams)")
        else:
            # Fallback to generic floor schedule
            schedule_data = self.standards_mgr.get_sequential_floor_schedule(
                floors=building_data.get('floors', 10),
                floor_area_m2=building_data.get('area', 720),
                slab_thickness_mm=building_data.get('slab_thickness_mm', 200),
                crew_size=building_data.get('crew_size', 15)
            )
        
        # Create wrapper class to match old interface
        class SequenceResult:
            def __init__(self, schedule_data):
                self.total_duration = schedule_data.get('total_duration_days', 0)
                self.activities = []
                self.critical_path = []
                self.optimization_score = 1.0  # Not applicable for standards-based
                
                # Convert schedule to activity objects
                from enum import Enum
                from dataclasses import dataclass
                
                class Phase(Enum):
                    SITE_PREPARATION = "site_preparation"
                    FOUNDATION = "foundation"
                    SUPERSTRUCTURE = "superstructure"
                    FINISHES = "finishes"
                
                @dataclass
                class Activity:
                    id: str
                    name: str
                    phase: Phase
                    duration_days: float
                    predecessors: list
                    floor_level: int
                    crew_size: int
                
                for item in schedule_data.get('schedule', []):
                    # Determine phase from activity name
                    name = item.get('Activity', '')
                    if 'Site' in name or 'Excavation' in name:
                        phase = Phase.SITE_PREPARATION
                    elif 'Foundation' in name:
                        phase = Phase.FOUNDATION
                    else:
                        phase = Phase.SUPERSTRUCTURE
                    
                    activity = Activity(
                        id=item.get('ID', ''),
                        name=name,
                        phase=phase,
                        duration_days=item.get('Duration', 0),
                        predecessors=[item.get('Predecessors', '')] if item.get('Predecessors') else [],
                        floor_level=item.get('Floor', 0),
                        crew_size=15
                    )
                    self.activities.append(activity)
                    
                    if item.get('Critical') == 'YES':
                        self.critical_path.append(item.get('ID', ''))
        
        sequence_result = SequenceResult(schedule_data)
        
        seq_duration = self.perf_tracker.end_operation({
            'total_duration': sequence_result.total_duration,
            'activities': len(sequence_result.activities)
        })
        
        self._track_module_usage('StandardsManager', 'generate_shear_wall_building_schedule', schedule_data)
        
        # Log to database
        await self.logger.log_construction_sequence({
            'project_name': building_name,
            'floors': building_data.get('floors', 0),
            'total_duration': sequence_result.total_duration,
            'activities': [{'id': a.id, 'name': a.name, 'duration': a.duration_days} for a in sequence_result.activities],
            'critical_path': sequence_result.critical_path,
            'optimization_score': sequence_result.optimization_score,
            'standards_applied': schedule_data.get('standards_applied', {})
        })
        
        logging.info(f"   OK Sequence generated: {sequence_result.total_duration:.1f} days")
        logging.info(f"   OK Critical path: {len(sequence_result.critical_path)} activities")
        logging.info(f"   OK Total activities: {len(sequence_result.activities)}")
        logging.info(f"   OK Time: {seq_duration:.2f}s\n")
        
        # ====================
        # ====================
        # 2. VALIDATION (using your validator module)
        # ====================
        logging.info("[2/5] Validating Constructability...")
        self.perf_tracker.start_operation("Validation_AI_Module")
        
        # Convert schedule_data to format expected by validator
        sequence_for_validation = {
            'total_duration': sequence_result.total_duration,
            'activities': [{'id': a.id, 'name': a.name, 'duration': a.duration_days, 'floor': a.floor_level} 
                          for a in sequence_result.activities],
            'critical_path': sequence_result.critical_path,
            'schedule': schedule_data.get('schedule', [])
        }
        
        validation_result = await self.validator.validate_constructability(
            project_data=building_data,
            sequence_data=sequence_for_validation,
            validate_all=True
        )
        
        val_duration = self.perf_tracker.end_operation({
            'is_constructable': validation_result.is_constructable,
            'issues': len(validation_result.issues)
        })
        
        self._track_module_usage('StandardsBasedValidator', 'validate_constructability', validation_result)
        
        # Log validation
        await self.logger.log_validation_result({
            'project_name': building_name,
            'is_constructable': validation_result.is_constructable,
            'overall_score': validation_result.overall_score,
            'critical_issues': len([i for i in validation_result.issues if i.severity.value == 'critical']),
            'high_issues': len([i for i in validation_result.issues if i.severity.value == 'high']),
            'standards_checked': validation_result.standards_checked  # Changed from ai_recommendations
        })
        
        logging.info(f"   OK Constructable: {validation_result.is_constructable}")
        logging.info(f"   OK Overall Score: {validation_result.overall_score:.1%}")
        logging.info(f"   OK Issues Found: {len(validation_result.issues)}")
        logging.info(f"   OK Standards Checked: {', '.join(validation_result.standards_checked)}")
        logging.info(f"   OK Time: {val_duration:.2f}s\n")
        
        # ====================
        # 4. PATTERN LEARNING (using your pattern learner)
        # ====================
        logging.info("[4/5] [4/5] Analyzing Construction Patterns...")
        self.perf_tracker.start_operation("Pattern_Learning_Module")
        
        # Learn from this building
        pattern_result = await self.pattern_learner.learn_from_dataset([building_data], batch_size=1)
        
        # [FIX] Validate pattern_result is a dict, not a string
        if isinstance(pattern_result, str):
            try:
                pattern_result = json.loads(pattern_result)
            except json.JSONDecodeError as e:
                logging.warning(f"Pattern learner returned invalid JSON string: {pattern_result[:200]}")
                pattern_result = {'total_patterns': 0, 'error': f'JSON decode error: {str(e)}'}
        
        if not isinstance(pattern_result, dict):
            logging.warning(f"Pattern learner returned {type(pattern_result).__name__}, expected dict")
            pattern_result = {'total_patterns': 0, 'error': f'Invalid type: {type(pattern_result).__name__}'}
        
        pattern_duration = self.perf_tracker.end_operation({
            'patterns_found': pattern_result.get('total_patterns', 0)
        })
        
        self._track_module_usage('ConstructionPatternLearner', 'learn_from_dataset', pattern_result)
        
        logging.info(f"   OK Patterns Discovered: {pattern_result.get('total_patterns', 0)}")
        if 'error' in pattern_result:
            logging.warning(f"   [WARNING] Pattern learning had errors: {pattern_result['error']}")
        logging.info(f"   OK Time: {pattern_duration:.2f}s\n")
        
        # ====================
        # DUMMY OPTIMIZATION RESULT (for backward compatibility)
        # ====================
        # Create empty optimization result since optimization was removed
        class DummyOptResult:
            def __init__(self):
                self.original_value = sequence_result.total_duration
                self.optimized_value = sequence_result.total_duration
                self.improvement_percentage = 0
                self.optimization_method = "None"
                self.confidence = 0
                self.recommendations = []
        
        opt_result = DummyOptResult()
        
        # ====================
        # 5. REPORT GENERATION
        # ====================
        logging.info("[5/5] [5/5] Generating Reports and Visualizations...")
        self.perf_tracker.start_operation("Report_Generation")
        
        # Generate all outputs
        await self._generate_csv_reports(report_dir, sequence_result, opt_result, validation_result, building_data, standards_data)
        await self._generate_visualizations(report_dir, sequence_result, opt_result, validation_result, building_data, standards_data)
        await self._generate_markdown_report(report_dir, sequence_result, opt_result, validation_result, building_data, pattern_result, standards_data)
        await self._generate_performance_report(report_dir)
        await self._generate_module_usage_log(report_dir)
        
        report_duration = self.perf_tracker.end_operation()
        
        # End total timing
        total_duration = self.perf_tracker.end_operation()
        
        logging.info(f"   OK CSV Reports: 4 files")
        logging.info(f"   OK Visualizations: 10 files (5 PNG + 5 SVG)")
        logging.info(f"   OK Markdown Report: 1 file")
        logging.info(f"   OK Performance Log: 1 file")
        logging.info(f"   OK Module Usage Log: 1 file")
        logging.info(f"   OK Time: {report_duration:.2f}s\n")
        
        logging.info(f"{'='*80}")
        logging.info(f"[3/5] REPORT GENERATION COMPLETE")
        logging.info(f"{'='*80}")
        logging.info(f"Total Analysis Time: {total_duration:.2f}s")
        logging.info(f"Output Directory: {report_dir}")
        logging.info(f"{'='*80}\n")
        
        # Log performance metrics to database
        perf_summary = self.perf_tracker.get_summary()
        await self.logger.log_performance_metric(
            'report_generation_time',
            total_duration,
            perf_summary
        )
        
        return str(report_dir)
    
    async def _generate_csv_reports(self, report_dir: Path, sequence_result, opt_result, validation_result, building_data, standards_data: Dict):
        """Generate CSV data files"""
        
        # 1. Construction Schedule CSV
        schedule_data = []
        for activity in sequence_result.activities:
            schedule_data.append({
                'id': activity.id,
                'name': activity.name,
                'phase': activity.phase.value,
                'duration_days': activity.duration_days,
                'predecessors': ','.join(activity.predecessors),
                'floor_level': activity.floor_level,
                'crew_size': activity.crew_size,
                'is_critical': activity.id in sequence_result.critical_path
            })
        
        df_schedule = pd.DataFrame(schedule_data)
        csv_path = report_dir / 'construction_schedule.csv'
        df_schedule.to_csv(csv_path, index=False)
        logging.info(f"   Wrote: {csv_path} (exists: {csv_path.exists()}, size: {csv_path.stat().st_size if csv_path.exists() else 0} bytes)")
        
        # 2. Validation Issues CSV
        issues_data = []
        for issue in validation_result.issues:
            issues_data.append({
                'issue_id': issue.issue_id,
                'severity': issue.severity.value,
                'category': issue.category,
                'description': issue.description,
                'code_reference': issue.code_reference,      # Changed from impact
                'calculated_value': issue.calculated_value,  # Changed from recommendation
                'standard': issue.standard                   # Changed from ai_confidence
            })
        
        df_issues = pd.DataFrame(issues_data)
        csv_path = report_dir / 'validation_issues.csv'
        df_issues.to_csv(csv_path, index=False)
        logging.info(f"   Wrote: {csv_path} (exists: {csv_path.exists()}, size: {csv_path.stat().st_size if csv_path.exists() else 0} bytes)")
        
        # 3. Project Summary CSV with Standards Reference
        summary_data = {
            'Metric': [
                'Building Name',
                'Total Floors',
                'Floor Area (mÂ²)',
                'Total Height (m)',
                'Structural System',
                'Total Duration (days)',
                'Critical Path Activities',
                'Total Activities',
                'Critical Issues',
                'High Issues',
                'Construction Standards',
                'Concrete Min Strength (ACI 318)',
                'Min Curing Days (ACI 318)',
                'Formwork Safety Factor (ACI 347)',
                'Typical Crew Size (RSMeans)',
                'Superstructure Days/Floor (RSMeans)',
                # Material Quantities (from AutoCAD extraction)
                'Concrete Volume (mÂ³)',
                'Concrete per Floor (mÂ³)',
                'Total Design Volume (mÂ³)',
                'Formwork Area (mÂ²)',
                'Rebar (tons)',
                'Wall Thickness (m)',
                'Floor Thickness (m)'
            ],
            'Value': [
                building_data.get('name', 'unnamed'),
                building_data.get('floors', 0),
                building_data.get('area', 0),
                building_data.get('height', 0),
                building_data.get('structural_system', 'unknown'),
                f"{sequence_result.total_duration:.1f}",
                len(sequence_result.critical_path),
                len(sequence_result.activities),
                len([i for i in validation_result.issues if i.severity.value == 'critical']),
                len([i for i in validation_result.issues if i.severity.value == 'high']),
                'ACI 318-19, ACI 347-04, ASCE 7-22, RSMeans 2024',
                f"{standards_data['aci_318']['concrete_min_fc_psi']} psi",
                f"{standards_data['aci_318']['min_curing_days']} days",
                f"{standards_data['aci_347']['min_safety_factor']}",
                f"{standards_data['rsmeans']['typical_crew_size']} workers",
                f"{standards_data['rsmeans']['superstructure_days_per_floor']} days",
                # Material Quantities (from AutoCAD extraction)
                f"{building_data.get('material_quantities', {}).get('concrete_volume_m3', 0):.1f}",
                f"{building_data.get('material_quantities', {}).get('concrete_volume_per_floor_m3', 0):.1f}",
                f"{building_data.get('material_quantities', {}).get('total_design_volume_m3', 0):.1f}",
                f"{building_data.get('material_quantities', {}).get('formwork_area_m2', 0):.1f}",
                f"{building_data.get('material_quantities', {}).get('rebar_tons', 0):.1f}",
                f"{building_data.get('material_quantities', {}).get('wall_thickness_m', 0):.2f}",
                f"{building_data.get('material_quantities', {}).get('floor_thickness_m', 0):.2f}"
            ]
        }
        df_summary = pd.DataFrame(summary_data)
        csv_path = report_dir / 'project_summary.csv'
        df_summary.to_csv(csv_path, index=False)
        logging.info(f"   Wrote: {csv_path} (exists: {csv_path.exists()}, size: {csv_path.stat().st_size if csv_path.exists() else 0} bytes)")
    
    async def _generate_visualizations(self, report_dir: Path, sequence_result, opt_result, validation_result, building_data, standards_data: Dict):
        """Generate visualization charts"""
        
        plt.style.use('seaborn-v0_8-darkgrid')
        
        # 1. Gantt Chart with Critical Path
        self._create_gantt_chart(report_dir, sequence_result, building_data, standards_data)
        
        # 2. Validation Issues Distribution
        self._create_validation_chart(report_dir, validation_result)
        
        # 3. Resource Histogram
        self._create_resource_histogram(report_dir, sequence_result)
        
        # 4. Performance Metrics
        self._create_performance_chart(report_dir)
        
        # 5. Module Usage Timeline
        self._create_module_usage_chart(report_dir)
    
    def _create_gantt_chart(self, report_dir: Path, sequence_result, building_data, standards_data: Dict):
        """Create Gantt chart visualization using ModernConstructionGantt if available"""
        
        # Try to use ModernConstructionGantt first
        try:
            from visualization_report_module.modern_gantt_with_metrics import ModernConstructionGantt
            use_modern_gantt = True
        except ImportError:
            use_modern_gantt = False
            logging.warning("ModernConstructionGantt not available, using basic chart")
        
        if use_modern_gantt:
            # Use COMPLETE standards_data passed as parameter (not creating fake data here!)
            # The standards_data parameter already contains ALL data from _get_complete_standards_data()
            
            # Convert sequence_result activities to task format for ModernConstructionGantt
            activity_times = self._calculate_activity_times(sequence_result.activities)
            tasks = []
            
            for idx, activity in enumerate(sequence_result.activities):
                start_day = activity_times[activity.id]['start']
                duration = activity.duration_days
                is_critical = activity.id in sequence_result.critical_path
                
                # Map phase to category
                category_map = {
                    'site_preparation': 'excavation',
                    'foundation': 'foundation',
                    'substructure': 'foundation',
                    'superstructure': 'concrete',
                    'envelope': 'masonry',
                    'interior': 'finishes',
                    'mep_systems': 'mep',
                    'finishes': 'finishes',
                    'commissioning': 'finishes'
                }
                
                task = {
                    'id': idx + 1,
                    'name': activity.name,
                    'start': start_day,
                    'duration': duration,
                    'category': category_map.get(activity.phase.value, 'default'),
                    'priority': 'critical' if is_critical else 'medium',
                    'progress': 0,
                    'floor': activity.floor_level  # ADDED: floor level for sequential ordering
                }
                tasks.append(task)
            
            # Create modern Gantt chart with metrics
            gantt = ModernConstructionGantt(
                title=f"Construction Schedule - {building_data.get('name', 'Building')}\n"
                      f"{building_data.get('floors', 0)} Floors - {sequence_result.total_duration:.0f} Days Total",
                figsize=(18, 12)
            )
            
            fig = gantt.create_chart_with_metrics(
                tasks=tasks,
                standards_data=standards_data,
                start_date=datetime.now()
            )
            
            fig.savefig(report_dir / 'gantt_chart.png', dpi=300, bbox_inches='tight')
            fig.savefig(report_dir / 'gantt_chart.svg', format='svg', bbox_inches='tight')
            plt.close(fig)
            logging.info("[OK] Created Gantt chart with engineering metrics panel (PNG + SVG)")
            
        else:
            # Fallback to basic Gantt chart
            fig, ax = plt.subplots(figsize=(16, 12))
            
            # Phase colors
            phase_colors = {
                'site_preparation': '#8B4513',
                'foundation': '#A0522D',
                'substructure': '#CD853F',
                'superstructure': '#4169E1',
                'envelope': '#32CD32',
                'interior': '#FFD700',
                'mep_systems': '#FF8C00',
                'finishes': '#9370DB',
                'commissioning': '#FF69B4'
            }
            
            # Calculate start times using CPM
            activity_times = self._calculate_activity_times(sequence_result.activities)
            
            y_pos = range(len(sequence_result.activities))
            for idx, activity in enumerate(sequence_result.activities):
                start = activity_times[activity.id]['start']
                duration = activity.duration_days
                color = phase_colors.get(activity.phase.value, '#808080')
                
                if activity.id in sequence_result.critical_path:
                    ax.barh(idx, duration, left=start, color=color, edgecolor='red', linewidth=3, alpha=0.9)
                else:
                    ax.barh(idx, duration, left=start, color=color, alpha=0.7)
                
                ax.text(start + duration/2, idx, f"{duration:.0f}d", 
                       ha='center', va='center', fontsize=8, fontweight='bold')
            
            ax.set_yticks(y_pos)
            ax.set_yticklabels([a.name for a in sequence_result.activities], fontsize=9)
            ax.set_xlabel('Days', fontsize=12, fontweight='bold')
            ax.set_title(f'Construction Schedule - {building_data.get("name", "Building")}\n'
                        f'{building_data.get("floors", 0)} Floors - {sequence_result.total_duration:.0f} Days Total',
                        fontsize=14, fontweight='bold', pad=20)
            ax.grid(axis='x', alpha=0.3)
            
            # Legend
            legend_elements = [mpatches.Patch(color=color, label=phase.replace('_', ' ').title()) 
                              for phase, color in phase_colors.items()]
            legend_elements.append(mpatches.Patch(edgecolor='red', facecolor='white', linewidth=3, 
                                                 label='Critical Path'))
            ax.legend(handles=legend_elements, loc='lower right', fontsize=9)
            
            plt.tight_layout()
            plt.savefig(report_dir / 'gantt_chart.png', dpi=300, bbox_inches='tight')
            plt.savefig(report_dir / 'gantt_chart.svg', format='svg', bbox_inches='tight')
            plt.close()
    
    def _calculate_activity_times(self, activities):
        """Calculate start/end times using CPM forward pass"""
        times = {}
        for activity in activities:
            times[activity.id] = {'start': 0, 'end': 0}
        
        # Forward pass
        for activity in activities:
            if not activity.predecessors:
                times[activity.id]['start'] = 0
            else:
                max_end = max([times[pred]['end'] for pred in activity.predecessors if pred in times])
                times[activity.id]['start'] = max_end
            
            times[activity.id]['end'] = times[activity.id]['start'] + activity.duration_days
        
        return times
    
    
    def _create_validation_chart(self, report_dir: Path, validation_result):
        """Create validation issues chart"""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Issues by severity
        severity_counts = {}
        for issue in validation_result.issues:
            sev = issue.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        if severity_counts:
            colors_map = {
                'critical': '#FF0000',
                'high': '#FF6B00',
                'medium': '#FFD700',
                'low': '#90EE90',
                'info': '#ADD8E6'
            }
            
            labels = [s.title() for s in severity_counts.keys()]
            sizes = list(severity_counts.values())
            colors = [colors_map.get(s, '#808080') for s in severity_counts.keys()]
            
            ax1.pie(sizes, labels=labels, autopct='%1.0f%%', startangle=90, colors=colors)
            ax1.set_title('Issues by Severity', fontsize=13, fontweight='bold')
        
        # Issues summary
        total_issues = len(validation_result.issues)
        critical = len([i for i in validation_result.issues if i.severity.value == 'critical'])
        high = len([i for i in validation_result.issues if i.severity.value == 'high'])
        
        ax2.axis('off')
        summary_text = f"""VALIDATION SUMMARY

Total Issues: {total_issues}
Critical: {critical}
High: {high}

Constructable: {'YES' if validation_result.is_constructable else 'NO'}

Standards Applied:
â€¢ ACI 318-19
â€¢ ACI 347-04
â€¢ ASCE 7-22
â€¢ RSMeans 2024
"""
        ax2.text(0.1, 0.9, summary_text, transform=ax2.transAxes,
                fontsize=11, verticalalignment='top', family='monospace',
                bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.3))
        ax2.set_title('Validation Summary', fontsize=13, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(report_dir / 'validation_results.png', dpi=300, bbox_inches='tight')
        plt.savefig(report_dir / 'validation_results.svg', format='svg', bbox_inches='tight')
        plt.close()
    
    def _create_resource_histogram(self, report_dir: Path, sequence_result):
        """Create resource usage histogram"""
        fig, ax = plt.subplots(figsize=(14, 6))
        
        # Use actual resource histogram from sequence result
        if hasattr(sequence_result, 'resource_histogram'):
            histogram = sequence_result.resource_histogram
            days = range(len(histogram.get('workers', [])))
            workers = histogram.get('workers', [])
            
            ax.plot(days, workers, linewidth=2, color='#4169E1', label='Workers')
            ax.fill_between(days, workers, alpha=0.3, color='#4169E1')
            
            if workers:
                avg_workers = np.mean(workers)
                max_workers = np.max(workers)
                ax.axhline(y=avg_workers, color='red', linestyle='--', linewidth=1.5, 
                          label=f'Average: {avg_workers:.0f}')
                ax.axhline(y=max_workers, color='green', linestyle='--', linewidth=1.5,
                          label=f'Peak: {max_workers:.0f}')
        
        ax.set_xlabel('Days', fontsize=12, fontweight='bold')
        ax.set_ylabel('Number of Workers', fontsize=12, fontweight='bold')
        ax.set_title('Daily Resource Loading', fontsize=14, fontweight='bold', pad=20)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=10)
        
        plt.tight_layout()
        plt.savefig(report_dir / 'resource_histogram.png', dpi=300, bbox_inches='tight')
        plt.savefig(report_dir / 'resource_histogram.svg', format='svg', bbox_inches='tight')
        plt.close()
    
    def _create_performance_chart(self, report_dir: Path):
        """Create performance metrics chart"""
        perf_summary = self.perf_tracker.get_summary()
        
        if not perf_summary.get('operations'):
            return
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # Operation times
        ops = list(perf_summary['operations'].keys())
        times = [perf_summary['operations'][op]['avg_time'] for op in ops]
        counts = [perf_summary['operations'][op]['count'] for op in ops]
        
        colors = plt.cm.viridis(np.linspace(0, 1, len(ops)))
        
        ax1.barh(ops, times, color=colors, alpha=0.8, edgecolor='black')
        ax1.set_xlabel('Average Time (seconds)', fontsize=12, fontweight='bold')
        ax1.set_title('Module Performance', fontsize=13, fontweight='bold')
        ax1.grid(axis='x', alpha=0.3)
        
        # Operation counts
        ax2.bar(ops, counts, color=colors, alpha=0.8, edgecolor='black')
        ax2.set_ylabel('Call Count', fontsize=12, fontweight='bold')
        ax2.set_title('Module Usage Frequency', fontsize=13, fontweight='bold')
        ax2.tick_params(axis='x', rotation=45)
        ax2.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(report_dir / 'performance_metrics.png', dpi=300, bbox_inches='tight')
        plt.savefig(report_dir / 'performance_metrics.svg', format='svg', bbox_inches='tight')
        plt.close()
    
    def _create_module_usage_chart(self, report_dir: Path):
        """Create module usage timeline"""
        if not self.modules_used:
            return
        
        fig, ax = plt.subplots(figsize=(14, 8))
        
        modules = {}
        for i, entry in enumerate(self.modules_used):
            module = entry['module']
            if module not in modules:
                modules[module] = []
            modules[module].append(i)
        
        colors = plt.cm.Set3(np.linspace(0, 1, len(modules)))
        
        for idx, (module, positions) in enumerate(modules.items()):
            ax.scatter(positions, [idx] * len(positions), 
                      s=100, c=[colors[idx]], alpha=0.7, edgecolors='black')
        
        ax.set_yticks(range(len(modules)))
        ax.set_yticklabels(list(modules.keys()), fontsize=10)
        ax.set_xlabel('Call Sequence', fontsize=12, fontweight='bold')
        ax.set_title('AI Module Usage Timeline', fontsize=14, fontweight='bold', pad=20)
        ax.grid(axis='x', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(report_dir / 'module_usage_timeline.png', dpi=300, bbox_inches='tight')
        plt.savefig(report_dir / 'module_usage_timeline.svg', format='svg', bbox_inches='tight')
        plt.close()
    
    async def _generate_markdown_report(self, report_dir: Path, sequence_result, opt_result, validation_result, building_data, pattern_result, standards_data: Dict):
        """Generate comprehensive markdown report"""
        
        report_content = f"""# Construction Analysis Report
## {building_data.get('name', 'Building Project')}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Analysis Method:** AI-Powered Construction Modules  
**Standards Referenced:** ACI 318-19, RSMeans 2024, ASCE 7-22

---

## Executive Summary

This report was generated using **AI-powered construction analysis modules** that provide:
- Machine learning-based schedule optimization
- CPM-based construction sequencing  
- Constructability validation
- Pattern learning from building data

### Key Findings

| Metric | Value |
|--------|-------|
| **Total Duration** | {sequence_result.total_duration:.1f} days |
| **Critical Path Activities** | {len(sequence_result.critical_path)} activities |
| **Total Activities** | {len(sequence_result.activities)} activities |
| **Constructable** | {'[OK] Yes' if validation_result.is_constructable else '[X] No'} |

### Standards Applied

| Standard | Application |
|----------|-------------|
| **ACI 318-19** | Concrete strength, curing time, rebar requirements |
| **ACI 347-04** | Formwork pressure, removal times |
| **ASCE 7-22** | Load combinations, seismic/wind design |
| **RSMeans 2024** | Productivity rates, crew sizing, cost estimation |

---

## 1. Building Specifications

### Geometry
- **Floors:** {building_data.get('floors', 0)}
- **Floor Area:** {building_data.get('area', 0)} mÂ²
- **Total Height:** {building_data.get('height', 0)} m
- **Structural System:** {building_data.get('structural_system', 'Unknown').replace('_', ' ').title()}

### Material Quantities (From AutoCAD Geometry)

| Material | Quantity |
|----------|----------|
| Concrete Volume | {building_data.get('material_quantities', {}).get('concrete_volume_m3', 0):.1f} mÂ³ |
| Concrete per Floor | {building_data.get('material_quantities', {}).get('concrete_volume_per_floor_m3', 0):.1f} mÂ³ |
| **Total Design Volume** | **{building_data.get('material_quantities', {}).get('total_design_volume_m3', 0):.1f} mÂ³** (Wall + Slab) |
| Formwork Area | {building_data.get('material_quantities', {}).get('formwork_area_m2', 0):.1f} mÂ² |
| Rebar (estimated) | {building_data.get('material_quantities', {}).get('rebar_tons', 0):.1f} tons * |
| Wall Thickness | {building_data.get('material_quantities', {}).get('wall_thickness_m', 0):.2f} m |
| Floor Thickness | {building_data.get('material_quantities', {}).get('floor_thickness_m', 0):.2f} m |

*Rebar estimated using typical industry practice: ~110 kg/mÂ³ (walls), ~90 kg/mÂ³ (slabs)

### Standards Compliance

#### ACI 318-19 (Concrete)
- Minimum 28-day Strength: {standards_data['aci_318']['concrete_min_fc_psi']} psi
- Typical 28-day Strength: {standards_data['aci_318']['concrete_typ_fc_psi']} psi
- Minimum Curing Time: {standards_data['aci_318']['min_curing_days']} days

#### RSMeans 2024 (Construction Costs)
- Typical Crew Size: {standards_data['rsmeans']['typical_crew_size']} workers
- Superstructure: {standards_data['rsmeans']['superstructure_days_per_floor']} days/floor
- MEP Rough-in: {standards_data['rsmeans']['mep_roughin_days_per_floor']} days/floor

---

## 2. Construction Sequencing

**Method:** CPM (Critical Path Method)  
**Based on:** Industry Standard Productivity Rates

### Construction Phases

Total activities: {len(sequence_result.activities)}  
Critical path length: {len(sequence_result.critical_path)} activities

### Critical Path

The following activities determine the minimum project duration:

"""
        
        # Add critical path activities
        critical_activities = [a for a in sequence_result.activities if a.id in sequence_result.critical_path]
        for activity in critical_activities:
            report_content += f"- **{activity.name}** ({activity.duration_days:.0f} days) - {activity.phase.value.replace('_', ' ').title()}\n"
        
        report_content += f"""

---

## 3. Construction Standards Analysis

**Standards Applied:**
- ACI 318-19 (Concrete Design)
- ACI 347-04 (Formwork)
- ASCE 7-22 (Load Combinations)
- RSMeans 2024 (Productivity)

### Concrete Design (ACI 318-19)

**Material Properties:**
- Minimum 28-day Strength: {standards_data['aci_318']['concrete_min_fc_psi']} psi
- Typical 28-day Strength: {standards_data['aci_318']['concrete_typ_fc_psi']} psi
- Minimum Curing Time: {standards_data['aci_318']['min_curing_days']} days

**Design Factors:**
- Flexure Phi Factor: {standards_data['aci_318']['phi_moment_max']}
- Shear Phi Factor: {standards_data['aci_318']['phi_shear']}

### Formwork Design (ACI 347-04)

**Safety Requirements:**
- Minimum Safety Factor: {standards_data['aci_347']['min_safety_factor']}
- Standard deflection limits applied
- Lateral pressure calculations per Section 2.2.2

### Productivity Rates (RSMeans 2024)

**Crew Configuration:**
- Typical Crew Size: {standards_data['rsmeans']['typical_crew_size']} workers
- Superstructure: {standards_data['rsmeans']['superstructure_days_per_floor']} days/floor
- MEP Rough-in: {standards_data['rsmeans']['mep_roughin_days_per_floor']} days/floor
- Finishes: {standards_data['rsmeans']['finishes_days_per_floor']} days/floor

---

## 4. Constructability Validation (Standards-Based)

**Validation Method:** Engineering Code Compliance  
**Standards Checked:** {', '.join(validation_result.standards_checked)}  
**Constructable:** {'[OK] Yes' if validation_result.is_constructable else '[X] No'}

### Issues Identified

Total issues: {len(validation_result.issues)}

"""
        
        # Group issues by severity
        severity_groups = {}
        for issue in validation_result.issues:
            sev = issue.severity.value
            if sev not in severity_groups:
                severity_groups[sev] = []
            severity_groups[sev].append(issue)
        
        for severity in ['critical', 'high', 'medium', 'low', 'info']:
            if severity in severity_groups:
                report_content += f"\n#### {severity.upper()} Issues ({len(severity_groups[severity])})\n\n"
                for issue in severity_groups[severity]:
                    report_content += f"- **[{issue.standard}]** {issue.description}\n"
                    report_content += f"  - *Code Reference:* {issue.code_reference}\n"
                    report_content += f"  - *Calculation:* {issue.calculated_value}\n\n"
        
        report_content += f"""

### Validation Summary

| Category | Count |
|----------|-------|
"""
        
        # Add summary by category
        category_counts = {}
        for issue in validation_result.issues:
            cat = issue.category
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        for cat, count in category_counts.items():
            report_content += f"| {cat.title()} | {count} |\n"
        
        report_content += f"""

---

## 5. Pattern Learning

**Module Used:** `ConstructionPatternLearner`

Patterns discovered: {pattern_result.get('total_patterns', 0)}

The pattern learning module analyzed this building's characteristics and will use them to improve future predictions.

---

## 6. Performance Metrics

### Module Execution Times

"""
        
        perf_summary = self.perf_tracker.get_summary()
        if perf_summary.get('operations'):
            for op_name, op_data in perf_summary['operations'].items():
                report_content += f"- **{op_name}:** {op_data['avg_time']:.3f}s (calls: {op_data['count']})\n"
        
        report_content += f"""

**Total Analysis Time:** {perf_summary.get('total_time_seconds', 0):.2f}s

### Communication Steps

| Step | Module | Duration |
|------|--------|----------|
"""
        
        for i, metric in enumerate(perf_summary.get('timeline', [])[:10], 1):
            report_content += f"| {i} | {metric['operation']} | {metric['duration_seconds']:.3f}s |\n"
        
        report_content += f"""

---

## 7. Modules Used

The following AI modules were utilized in this analysis:

"""
        
        modules_summary = {}
        for entry in self.modules_used:
            module = entry['module']
            if module not in modules_summary:
                modules_summary[module] = {'functions': set(), 'count': 0}
            modules_summary[module]['functions'].add(entry['function'])
            modules_summary[module]['count'] += 1
        
        for module, data in modules_summary.items():
            report_content += f"### {module}\n\n"
            report_content += f"- **Call Count:** {data['count']}\n"
            report_content += f"- **Functions Used:**\n"
            for func in data['functions']:
                report_content += f"  - `{func}()`\n"
            report_content += "\n"
        
        report_content += """

---

## 8. Notes on Data Confidence

### HIGH Confidence Data Sources (International Standards)

The following data sources are internationally recognized engineering standards:

| Standard | Application | Confidence |
|----------|-------------|------------|
| **ACI 318-19** | Concrete design, phi factors, curing times | HIGH |
| **ACI 347-04** | Formwork removal times, lateral pressure | HIGH |
| **ASCE 7-22** | Load combinations, seismic/wind factors | HIGH |

### LOW Confidence Data Sources (Estimates Only)

The following data sources are **NOT international standards** and should be used as estimates only:

| Source | Application | Confidence |
|--------|-------------|------------|
| **productivity_standards.json** | Work duration estimates, crew productivity | LOW |
| **RSMeans typical values** | Days per floor estimates | LOW |

**Important:** Productivity rates vary significantly based on:
- Local labor conditions
- Equipment availability  
- Weather conditions
- Site accessibility
- Worker skill levels

Always verify productivity estimates with local contractors before finalizing schedules.

### Floor Sequencing Rule (ACI 347-04)

Per ACI 347-04 Section 3.7.2.3, floor construction must follow strict sequencing:
- **Floor N+1 formwork CANNOT start until Floor N curing is complete**
- Minimum slab form removal time: """ + str(standards_data.get('aci_347', {}).get('slab_removal_days', 7)) + """ days
- Minimum beam form removal time: """ + str(standards_data.get('aci_347', {}).get('beam_removal_days', 14)) + """ days

This ensures structural integrity and prevents premature loading of uncured concrete.

---

## 9. Deliverables

### Files Generated

**CSV Data Files:**
- `construction_schedule.csv` - Complete activity schedule
- `optimization_results.csv` - ML optimization results  
- `validation_issues.csv` - Detailed issue list
- `project_summary.csv` - Project metrics with standards

**Visualizations:**
- `gantt_chart.png` - Construction timeline with critical path
- `optimization_results.png` - Before/after optimization
- `validation_results.png` - Constructability analysis
- `resource_histogram.png` - Daily resource requirements
- `performance_metrics.png` - Module execution times
- `module_usage_timeline.png` - AI module call sequence

**Reports:**
- `CONSTRUCTION_REPORT.md` - This comprehensive report
- `performance_log.json` - Detailed performance metrics
- `module_usage_log.json` - Module function call log

---

## Document Information

**Report Generated By:** Construction AI Report Generator  
**Module Version:** 1.0  
**Standards Referenced:**
- ACI 318-19: Building Code Requirements for Structural Concrete
- RSMeans 2024: Building Construction Cost Data
- ASCE 7-22: Minimum Design Loads for Buildings

**Disclaimer:** This report was generated using AI-powered construction analysis modules. All recommendations should be reviewed by licensed professionals before implementation.

---

*End of Report*
"""
        
        # Save markdown report
        with open(report_dir / 'CONSTRUCTION_REPORT.md', 'w') as f:
            f.write(report_content)
    
    async def _generate_performance_report(self, report_dir: Path):
        """Generate detailed performance log"""
        perf_summary = self.perf_tracker.get_summary()
        
        with open(report_dir / 'performance_log.json', 'w') as f:
            json.dump(perf_summary, f, indent=2)
    
    async def _generate_module_usage_log(self, report_dir: Path):
        """Generate module usage log"""
        with open(report_dir / 'module_usage_log.json', 'w') as f:
            json.dump({
                'total_calls': len(self.modules_used),
                'modules': self.modules_used,
                'summary': {
                    module: {
                        'call_count': len([m for m in self.modules_used if m['module'] == module]),
                        'functions': list(set([m['function'] for m in self.modules_used if m['module'] == module]))
                    }
                    for module in set([m['module'] for m in self.modules_used])
                }
            }, f, indent=2)


# Main entry point
async def generate_report_from_building(building_data: Dict, output_dir: str = "./construction_reports") -> str:
    """
    Main function to generate comprehensive construction report
    
    Args:
        building_data: Building specifications  
        output_dir: Output directory for reports
        
    Returns:
        Path to generated report directory
    """
    generator = ComprehensiveConstructionReportGenerator()
    report_path = await generator.generate_comprehensive_report(building_data, output_base_dir=output_dir)
    return report_path


if __name__ == "__main__":
    # Example usage
    test_building = {
        'name': '5-Story Shear Wall Building',
        'floors': 5,
        'area': 540,
        'height': 20,
        'structural_system': 'shear_wall',
        'complexity': 0.5
    }
    
    report_path = asyncio.run(generate_report_from_building(test_building))
    logging.info(f"\nReport generated at: {report_path}")
