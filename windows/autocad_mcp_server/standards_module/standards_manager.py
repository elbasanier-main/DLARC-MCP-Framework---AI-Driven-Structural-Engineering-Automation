"""
Standards Manager - Main query interface for all building standards
UPDATED: Enhanced ACI 347-04 form removal time calculations for proper floor sequencing
"""

import json
import os
import sys
import math
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

# Configure logging to stderr (not stdout) to avoid breaking MCP JSON
logging.basicConfig(level=logging.WARNING, format='%(message)s', stream=sys.stderr)

class StandardsManager:
    """
    Central manager for querying building design standards
    Supports: ASCE 7-22, ACI 318-19, ACI 347-04, AISC 360, IFC4, RSMeans, Construction Productivity
    """
    
    def __init__(self):
        self.data_dir = Path(__file__).parent / 'data'
        self._cache = {}
        self._load_all_standards()
    
    def _load_all_standards(self):
        """Load all JSON standard files into memory"""
        standard_files = [
            ('aci_318_concrete', 'materials/aci_318_concrete.json'),
            ('aci_318_complete', 'materials/aci_318_complete.json'),
            ('aisc_360_steel', 'materials/aisc_360_steel.json'),
            ('asce_7_22_combinations', 'loads/asce_7_22_combinations.json'),
            ('ifc4_mappings', 'codes/ifc4_mappings.json'),
            ('construction_sequences', 'codes/construction_sequences.json'),
            ('aci_347_formwork', 'construction/aci_347_formwork.json'),
            ('productivity_standards', 'construction/productivity_standards.json')
        ]
        
        loaded_count = 0
        failed_files = []
        
        for cache_key, file_path in standard_files:
            try:
                data = self._load_json(file_path)
                if data:
                    self._cache[cache_key] = data
                    loaded_count += 1
                else:
                    failed_files.append(file_path)
                    self._cache[cache_key] = {}
            except Exception as e:
                logging.warning(f"Failed to load {file_path}: {e}")
                failed_files.append(file_path)
                self._cache[cache_key] = {}
        
        if failed_files:
            logging.warning(f"Could not load {len(failed_files)}/{len(standard_files)} standards files")
        else:
            logging.info(f"Successfully loaded all {loaded_count} standards files")
    
    def _load_json(self, rel_path: str) -> Dict:
        """Load a JSON file with multiple encoding attempts for Korean Windows"""
        file_path = self.data_dir / rel_path
        
        # Try multiple encodings common in Korean Windows systems
        encodings = ['utf-8', 'utf-8-sig', 'cp949', 'euc-kr', 'latin-1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return json.load(f)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        
        # If all encodings fail, return empty dict
        logging.warning(f"Could not load {rel_path} with any encoding")
        return {}
    
    # ==================== Material Queries ====================
    
    def get_material(self, standard: str, grade: str) -> Optional[Dict]:
        """
        Get material properties
        
        Args:
            standard: 'ACI_318' or 'AISC_360'
            grade: Material grade (e.g., 'C30/37', 'A992')
        
        Returns:
            Dict with material properties or None
        """
        if standard == 'ACI_318':
            data = self._cache.get('aci_318_concrete', {})
            return data.get('materials', {}).get(grade)
        elif standard == 'AISC_360':
            data = self._cache.get('aisc_360_steel', {})
            return data.get('materials', {}).get(grade)
        return None
    
    def list_materials(self, standard: str) -> List[str]:
        """List all available material grades for a standard"""
        if standard == 'ACI_318':
            data = self._cache.get('aci_318_concrete', {})
            return list(data.get('materials', {}).keys())
        elif standard == 'AISC_360':
            data = self._cache.get('aisc_360_steel', {})
            return list(data.get('materials', {}).keys())
        return []
    
    # ==================== ACI 318-19 Complete Queries (NEW) ====================
    
    def get_phi_factor(self, member_type: str, strain_condition: Optional[str] = None) -> Dict[str, Any]:
        """Get strength reduction factor (phi) from ACI 318-19"""
        data = self._cache.get('aci_318_complete', {})
        strength_factors = data.get('ACI_318_19_Complete_Standards', {}).get('strength_reduction_factors', {})
        
        mapping = {
            "moment": "moment_axial",
            "axial": "moment_axial",
            "shear": "shear",
            "torsion": "torsion",
            "bearing": "bearing",
            "post_tensioned": "post_tensioned_anchorage",
            "bracket": "brackets_corbels"
        }
        
        key = mapping.get(member_type.lower(), member_type)
        return strength_factors.get('values', {}).get(key, {})
    
    def get_concrete_properties(self, fc_psi: Optional[float] = None) -> Dict[str, Any]:
        """Get concrete material properties from ACI 318-19"""
        data = self._cache.get('aci_318_complete', {})
        concrete_props = data.get('ACI_318_19_Complete_Standards', {}).get('concrete_properties', {})
        
        if fc_psi:
            # Calculate specific properties
            wc = 145  # normal weight concrete
            Ec = 57000 * math.sqrt(fc_psi)
            
            return {
                "fc_psi": fc_psi,
                "Ec_psi": Ec,
                "poissons_ratio": 0.2,
                "formula_used": "Ec = 57000 * sqrt(fc')"
            }
        
        return concrete_props
    
    def get_rebar_properties(self, grade: str = "60") -> Dict[str, Any]:
        """Get reinforcement properties from ACI 318-19"""
        data = self._cache.get('aci_318_complete', {})
        steel_props = data.get('ACI_318_19_Complete_Standards', {}).get('steel_properties', {})
        return steel_props
    
    def get_development_length(self, bar_size: str, fc_psi: float, fy_psi: float = 60000) -> Dict[str, Any]:
        """Calculate development length from ACI 318-19"""
        data = self._cache.get('aci_318_complete', {})
        formulas = data.get('ACI_318_19_Complete_Standards', {}).get('development_length_tension', {})
        
        db = float(bar_size.replace("#", "")) / 8  # bar diameter in inches
        
        # Simplified formula with default factors
        psi_t = 1.0  # uncoated
        psi_e = 1.0  # #6 and smaller
        psi_s = 1.3  # conservative
        lambda_factor = 1.0  # normal weight
        
        # ld = (fy*psi_t*psi_e*psi_s)/(25*lambda*sqrt(fc)) * db
        ld = (fy_psi * psi_t * psi_e * psi_s) / (25 * lambda_factor * math.sqrt(fc_psi)) * db
        
        return {
            "ld_inches": ld,
            "bar_size": bar_size,
            "db_inches": db,
            "fc_psi": fc_psi,
            "fy_psi": fy_psi,
            "factors": {
                "psi_t": psi_t,
                "psi_e": psi_e,
                "psi_s": psi_s,
                "lambda": lambda_factor
            },
            "formula": formulas.get("simplified_formula"),
            "reference": formulas.get("reference")
        }
    
    def get_beam_shear_capacity(self, bw: float, d: float, fc_psi: float) -> Dict[str, Any]:
        """Calculate beam shear capacity from ACI 318-19"""
        # Vc = 2 * lambda * sqrt(fc') * bw * d
        lambda_factor = 1.0  # normal weight concrete
        Vc = 2 * lambda_factor * math.sqrt(fc_psi) * bw * d
        phi = 0.75
        
        return {
            "Vc_lbs": Vc,
            "phi_Vc_lbs": phi * Vc,
            "bw_inches": bw,
            "d_inches": d,
            "fc_psi": fc_psi,
            "phi": phi,
            "formula": "Vc = 2 * lambda * sqrt(fc') * bw * d"
        }
    
    # ==================== ACI 347-04 Formwork Queries (ENHANCED) ====================
    
    def get_formwork_loads(self, use_motorized_carts: bool = False) -> Dict[str, Any]:
        """Get formwork vertical loads from ACI 347-04"""
        data = self._cache.get('aci_347_formwork', {})
        vertical_loads = data.get('ACI_347_04_Formwork_Guide', {}).get('vertical_loads', {})
        
        if use_motorized_carts:
            return vertical_loads.get('live_load', {}).get('minimum_values', {}).get('with_motorized_carts', {})
        else:
            return vertical_loads.get('live_load', {}).get('minimum_values', {}).get('without_motorized_carts', {})
    
    def get_lateral_pressure(self, placement_rate: float, temperature: float = 70, 
                            slump: float = 4, concrete_height: float = 10) -> Dict[str, Any]:
        """Calculate lateral pressure on formwork from ACI 347-04"""
        data = self._cache.get('aci_347_formwork', {})
        formulas = data.get('ACI_347_04_Formwork_Guide', {}).get('lateral_pressure_concrete', {})
        
        # ACI formula: p = 150 + 9000*R/T
        R = placement_rate  # ft/hr
        T = temperature  # F
        
        p_max = 150 + (9000 * R / T)
        p_max = min(p_max, 2000)  # max 2000 psf
        p_max = min(p_max, 150 * concrete_height)  # or 150h
        
        return {
            "lateral_pressure_psf": p_max,
            "placement_rate_ft_hr": R,
            "temperature_F": T,
            "height_ft": concrete_height,
            "formula": "p = 150 + 9000*R/T",
            "max_limits": ["2000 psf", "150h psf"],
            "reference": formulas.get("reference", "ACI 347-04")
        }
    
    def get_formwork_removal_time(self, member_type: str = "slab", 
                                   span_ft: float = 15.0,
                                   live_vs_dead: str = "live_less_dead",
                                   use_reshores: bool = True,
                                   temperature_F: float = 70.0) -> Dict[str, Any]:
        """
        Get minimum formwork removal time from ACI 347-04 Section 3.7.2.3
        
        CRITICAL for sequential floor scheduling - determines when next floor can start
        
        Args:
            member_type: 'column', 'wall', 'slab', 'beam', 'joist'
            span_ft: Span length in feet (for slabs/beams)
            live_vs_dead: 'live_less_dead' or 'live_more_dead' (load ratio)
            use_reshores: Whether reshores will be placed after stripping
            temperature_F: Ambient temperature (must be above 50F)
        
        Returns:
            Dict with removal time in days and conditions
        """
        data = self._cache.get('aci_347_formwork', {})
        removal_times = data.get('ACI_347_04_Formwork_Guide', {}).get('form_removal_times', {})
        
        result = {
            "member_type": member_type,
            "span_ft": span_ft,
            "load_condition": live_vs_dead,
            "use_reshores": use_reshores,
            "temperature_F": temperature_F,
            "standard": "ACI 347-04",
            "reference": "Section 3.7.2.3",
            "confidence": "HIGH"  # International standard
        }
        
        # Vertical elements (columns, walls) - 12 hours
        if member_type.lower() in ['column', 'columns', 'wall', 'walls']:
            vertical = removal_times.get('vertical_elements', {})
            time_hours = vertical.get(member_type.lower() + 's', {}).get('time_hours', 
                         vertical.get(member_type.lower(), {}).get('time_hours', 12))
            result["removal_time_hours"] = time_hours
            result["removal_time_days"] = time_hours / 24.0
            result["note"] = "Vertical elements - does not support slab loads"
            return result
        
        # Determine span category
        if span_ft < 10:
            span_category = "under_10_ft_span"
        elif span_ft <= 20:
            span_category = "10_to_20_ft_span"
        else:
            span_category = "over_20_ft_span"
        
        # Get data based on member type
        if member_type.lower() in ['slab', 'slabs', 'floor_slab', 'one_way_slab']:
            slab_data = removal_times.get('one_way_floor_slabs', {}).get(span_category, {})
            load_data = slab_data.get(live_vs_dead, {})
            
            if use_reshores:
                time_days = load_data.get('time_days_no_shores', load_data.get('time_days', 7))
            else:
                time_days = load_data.get('time_days', 7)
            
            min_days = load_data.get('minimum_days', 3)
            result["removal_time_days"] = max(time_days, min_days)
            result["minimum_days"] = min_days
            
        elif member_type.lower() in ['beam', 'beams', 'girder', 'joist']:
            beam_data = removal_times.get('joist_beam_girder_soffits', {}).get(span_category, {})
            load_data = beam_data.get(live_vs_dead, {})
            
            if use_reshores:
                time_days = load_data.get('time_days_no_shores', load_data.get('time_days', 14))
            else:
                time_days = load_data.get('time_days', 14)
            
            min_days = load_data.get('minimum_days', 3)
            result["removal_time_days"] = max(time_days, min_days)
            result["minimum_days"] = min_days
            
        elif member_type.lower() in ['pan_joist', 'pan']:
            pan_data = removal_times.get('pan_joist_forms', {})
            if span_ft <= 30:
                result["removal_time_days"] = pan_data.get('30_in_or_less', {}).get('time_days', 3)
            else:
                result["removal_time_days"] = pan_data.get('over_30_in', {}).get('time_days', 4)
        else:
            # Default to slab values
            result["removal_time_days"] = 7
            result["note"] = "Default value - specific member type not found"
        
        # Temperature adjustment warning
        if temperature_F < 50:
            result["warning"] = "Temperature below 50F - increase removal time per ACI 347-04"
            result["removal_time_days"] = result.get("removal_time_days", 7) * 1.5
        
        return result
    
    def get_floor_cycle_time(self, floor_area_m2: float, 
                             slab_thickness_mm: float = 150,
                             span_ft: float = 15.0,
                             crew_size: int = 15,
                             temperature_F: float = 70.0) -> Dict[str, Any]:
        """
        Calculate minimum floor cycle time based on ACI 347-04 form removal requirements
        
        This determines the minimum time between starting consecutive floors
        
        Args:
            floor_area_m2: Floor area in square meters
            slab_thickness_mm: Slab thickness in mm
            span_ft: Typical span in feet
            crew_size: Crew size for productivity calculations
            temperature_F: Ambient temperature
        
        Returns:
            Dict with floor cycle time and breakdown
        """
        # Get form removal time (ACI 347-04) - HIGH confidence international standard
        slab_removal = self.get_formwork_removal_time(
            member_type="slab",
            span_ft=span_ft,
            live_vs_dead="live_less_dead",
            use_reshores=True,
            temperature_F=temperature_F
        )
        
        # ACI 318-19 minimum curing requirement
        min_curing_days = 7  # ACI 318-19 Table 26.1.3.5
        
        # Form removal time is the controlling factor for floor cycle
        form_removal_days = slab_removal.get("removal_time_days", 7)
        
        # Calculate work durations (from productivity - LOWER confidence)
        volume_m3 = floor_area_m2 * (slab_thickness_mm / 1000)
        rebar_kg = volume_m3 * 100  # Typical 100 kg/m3
        
        formwork_duration = self.calculate_labor_duration("shuttering", floor_area_m2, crew_size)
        rebar_duration = self.calculate_labor_duration("fixing_slabs_footings", rebar_kg, crew_size)
        concrete_duration = self.calculate_labor_duration("manual_laying", volume_m3, crew_size)
        
        # Construction work days
        formwork_days = formwork_duration.get("duration_days", 5)
        rebar_days = rebar_duration.get("duration_days", 4)
        concrete_days = concrete_duration.get("duration_days", 2)
        
        # Total work time before curing starts
        construction_days = formwork_days + rebar_days + concrete_days
        
        # Floor cycle = construction + max(form_removal, curing)
        wait_time = max(form_removal_days, min_curing_days)
        floor_cycle_days = construction_days + wait_time
        
        return {
            "floor_cycle_days": round(floor_cycle_days, 1),
            "breakdown": {
                "formwork_days": round(formwork_days, 1),
                "rebar_days": round(rebar_days, 1),
                "concrete_days": round(concrete_days, 1),
                "construction_subtotal": round(construction_days, 1),
                "form_removal_days": round(form_removal_days, 1),
                "min_curing_days": min_curing_days,
                "wait_time_days": round(wait_time, 1)
            },
            "standards_applied": {
                "ACI_347_04": {
                    "description": "Form removal time",
                    "value_days": form_removal_days,
                    "confidence": "HIGH"
                },
                "ACI_318_19": {
                    "description": "Minimum curing",
                    "value_days": min_curing_days,
                    "confidence": "HIGH"
                },
                "productivity_standards": {
                    "description": "Work duration estimates",
                    "confidence": "LOW - not international standard"
                }
            },
            "controlling_factor": "ACI 347-04 form removal" if form_removal_days >= min_curing_days else "ACI 318-19 curing"
        }
    
    def get_sequential_floor_schedule(self, floors: int,
                                       floor_area_m2: float,
                                       slab_thickness_mm: float = 150,
                                       span_ft: float = 15.0,
                                       crew_size: int = 15,
                                       temperature_F: float = 70.0) -> Dict[str, Any]:
        """
        Generate strictly sequential floor schedule based on ACI 347-04
        
        CRITICAL: Floors MUST be built in order (1, 2, 3, ..., N)
        Next floor cannot start until previous floor form removal time is complete
        
        Args:
            floors: Number of floors
            floor_area_m2: Floor area per floor
            slab_thickness_mm: Slab thickness
            span_ft: Typical span
            crew_size: Crew size
            temperature_F: Ambient temperature
        
        Returns:
            Dict with sequential schedule and floor start days
        """
        floor_cycle = self.get_floor_cycle_time(
            floor_area_m2=floor_area_m2,
            slab_thickness_mm=slab_thickness_mm,
            span_ft=span_ft,
            crew_size=crew_size,
            temperature_F=temperature_F
        )
        
        cycle_days = floor_cycle["floor_cycle_days"]
        breakdown = floor_cycle["breakdown"]
        
        schedule = []
        current_day = 0
        
        for floor_num in range(1, floors + 1):
            floor_start = current_day
            
            # Add activities for this floor in strict sequence
            activities = []
            
            # Formwork
            activities.append({
                "activity": f"Floor_{floor_num}_Formwork",
                "floor": floor_num,
                "start_day": round(floor_start, 1),
                "duration_days": breakdown["formwork_days"],
                "end_day": round(floor_start + breakdown["formwork_days"], 1),
                "source": "productivity_standards",
                "confidence": "LOW"
            })
            
            # Rebar (after formwork)
            rebar_start = floor_start + breakdown["formwork_days"]
            activities.append({
                "activity": f"Floor_{floor_num}_Rebar",
                "floor": floor_num,
                "start_day": round(rebar_start, 1),
                "duration_days": breakdown["rebar_days"],
                "end_day": round(rebar_start + breakdown["rebar_days"], 1),
                "source": "productivity_standards",
                "confidence": "LOW"
            })
            
            # Concrete (after rebar)
            concrete_start = rebar_start + breakdown["rebar_days"]
            activities.append({
                "activity": f"Floor_{floor_num}_Concrete",
                "floor": floor_num,
                "start_day": round(concrete_start, 1),
                "duration_days": breakdown["concrete_days"],
                "end_day": round(concrete_start + breakdown["concrete_days"], 1),
                "source": "productivity_standards",
                "confidence": "LOW"
            })
            
            # Curing/Form Removal (CRITICAL - from ACI 347-04)
            curing_start = concrete_start + breakdown["concrete_days"]
            activities.append({
                "activity": f"Floor_{floor_num}_Curing",
                "floor": floor_num,
                "start_day": round(curing_start, 1),
                "duration_days": breakdown["wait_time_days"],
                "end_day": round(curing_start + breakdown["wait_time_days"], 1),
                "source": "ACI_347-04 / ACI_318-19",
                "confidence": "HIGH",
                "note": f"Minimum {breakdown['form_removal_days']} days form removal per ACI 347-04"
            })
            
            schedule.append({
                "floor": floor_num,
                "start_day": round(floor_start, 1),
                "end_day": round(curing_start + breakdown["wait_time_days"], 1),
                "cycle_days": cycle_days,
                "activities": activities
            })
            
            # Next floor starts after this floor's curing is complete
            current_day = curing_start + breakdown["wait_time_days"]
        
        total_duration = current_day
        
        return {
            "floors": floors,
            "floor_cycle_days": cycle_days,
            "total_duration_days": round(total_duration, 1),
            "schedule": schedule,
            "standards_compliance": {
                "ACI_347-04": "Form removal times enforced",
                "ACI_318-19": "Minimum curing days enforced",
                "floor_sequence": "STRICTLY SEQUENTIAL (1, 2, 3, ..., N)"
            },
            "notes": [
                "Floor N+1 CANNOT start until Floor N curing is complete",
                "This is required by ACI 347-04 for structural safety",
                "Productivity estimates have LOW confidence - adjust based on actual site conditions"
            ]
        }
    
    def generate_shear_wall_building_schedule(self, 
                                               building_data: Dict[str, Any],
                                               crew_size: int = 15,
                                               temperature_F: float = 70.0) -> Dict[str, Any]:
        """
        Generate complete construction schedule for SHEAR WALL building
        
        CRITICAL: Shear wall buildings have NO BEAMS - only walls and slabs
        
        Schedule structure per floor:
        1. Floor N Walls (formwork + rebar + pour for walls)
        2. Floor N Slab Formwork
        3. Floor N Slab Rebar
        4. Floor N Pour (slab concrete)
        5. Floor N Curing (ACI 347-04 minimum)
        
        Args:
            building_data: Dict with floors, wall_area, slab_area, etc.
            crew_size: Number of workers
            temperature_F: Ambient temperature for curing adjustment
        
        Returns:
            Dict with complete sequential schedule matching realistic_schedule.csv format
        """
        floors = building_data.get('floors', 10)
        wall_area_m2 = building_data.get('wall_area_m2', 0)
        slab_area_m2 = building_data.get('floor_area_per_floor_m2', 720)
        wall_thickness_m = building_data.get('wall_thickness_m', 0.3)
        slab_thickness_mm = building_data.get('floor_thickness_m', 0.2) * 1000
        
        # Calculate per-floor quantities
        wall_area_per_floor = wall_area_m2 / floors if wall_area_m2 > 0 else slab_area_m2 * 0.4
        wall_volume_per_floor = wall_area_per_floor * wall_thickness_m
        slab_volume_per_floor = slab_area_m2 * (slab_thickness_mm / 1000)
        
        # Get ACI 347-04 curing time (HIGH confidence)
        slab_removal = self.get_formwork_removal_time(
            member_type="slab", span_ft=15.0, 
            live_vs_dead="live_less_dead", temperature_F=temperature_F
        )
        curing_days = max(slab_removal.get("removal_time_days", 7), 7)  # Minimum 7 days
        
        # Calculate durations using productivity rates (LOW confidence)
        # Wall work: formwork + rebar + concrete combined
        wall_rebar_kg = wall_volume_per_floor * 110  # 110 kg/m3 for walls
        wall_formwork = self.calculate_labor_duration("shuttering", wall_area_per_floor * 2, crew_size)  # Both sides
        wall_rebar = self.calculate_labor_duration("fixing_walls_columns", wall_rebar_kg, crew_size)
        
        # Fallback if fixing_walls_columns task not found
        if wall_rebar.get("error"):
            wall_rebar = self.calculate_labor_duration("fixing_slabs_footings", wall_rebar_kg, crew_size)
        if wall_rebar.get("error"):
            wall_rebar = {"duration_days": wall_rebar_kg / (crew_size * 100)}  # Default: 100 kg/worker/day
            
        wall_concrete = self.calculate_labor_duration("manual_laying", wall_volume_per_floor, crew_size)
        if wall_concrete.get("error"):
            wall_concrete = {"duration_days": wall_volume_per_floor / (crew_size * 2)}  # Default: 2 m3/worker/day
        
        wall_days = (wall_formwork.get("duration_days", 10) + 
                    wall_rebar.get("duration_days", 10) + 
                    wall_concrete.get("duration_days", 2))
        
        # Slab work: formwork, rebar, concrete separate
        slab_rebar_kg = slab_volume_per_floor * 90  # 90 kg/m3 for slabs
        slab_formwork = self.calculate_labor_duration("shuttering", slab_area_m2, crew_size)
        slab_rebar = self.calculate_labor_duration("fixing_slabs_footings", slab_rebar_kg, crew_size)
        slab_concrete = self.calculate_labor_duration("manual_laying", slab_volume_per_floor, crew_size)
        
        # Fallbacks for missing tasks
        if slab_formwork.get("error"):
            slab_formwork = {"duration_days": slab_area_m2 / (crew_size * 3)}  # Default: 3 m2/worker/day
        if slab_rebar.get("error"):
            slab_rebar = {"duration_days": slab_rebar_kg / (crew_size * 100)}  # Default: 100 kg/worker/day
        if slab_concrete.get("error"):
            slab_concrete = {"duration_days": slab_volume_per_floor / (crew_size * 2)}  # Default: 2 m3/worker/day
        if wall_formwork.get("error"):
            wall_formwork = {"duration_days": (wall_area_per_floor * 2) / (crew_size * 3)}  # Default
        
        slab_formwork_days = slab_formwork.get("duration_days", 27)
        slab_rebar_days = slab_rebar.get("duration_days", 21.6)
        slab_pour_days = max(slab_concrete.get("duration_days", 1), 1)  # Minimum 1 day
        
        # Build schedule
        schedule = []
        current_day = 0
        activity_id = 0
        
        # Site Preparation (pre-construction)
        schedule.append({
            "ID": f"A{activity_id:03d}",
            "Activity": "Site Preparation",
            "Floor": 0,
            "Duration": 5,
            "Early Start": current_day,
            "Early Finish": current_day + 5,
            "Late Start": current_day,
            "Late Finish": current_day + 5,
            "Float": 0,
            "Critical": "NO",
            "Predecessors": "",
            "Standard": "RSMeans",
            "Confidence": "LOW"
        })
        current_day += 5
        activity_id += 1
        
        # Excavation
        schedule.append({
            "ID": f"A{activity_id:03d}",
            "Activity": "Excavation",
            "Floor": 0,
            "Duration": 5,
            "Early Start": current_day,
            "Early Finish": current_day + 5,
            "Late Start": current_day,
            "Late Finish": current_day + 5,
            "Float": 0,
            "Critical": "NO",
            "Predecessors": f"A{activity_id-1:03d}",
            "Standard": "Productivity",
            "Confidence": "LOW"
        })
        current_day += 5
        activity_id += 1
        
        # Foundation work
        foundation_activities = [
            ("Foundation Formwork", 10.8, "Productivity"),
            ("Foundation Rebar", 13.0, "Productivity"),
            ("Foundation Pour", 2.2, "Productivity"),
            ("Foundation Curing", curing_days, "ACI 347-04 Sec 3.7.2.3")
        ]
        
        for name, duration, standard in foundation_activities:
            schedule.append({
                "ID": f"A{activity_id:03d}",
                "Activity": name,
                "Floor": 0,
                "Duration": round(duration, 1),
                "Early Start": round(current_day, 1),
                "Early Finish": round(current_day + duration, 1),
                "Late Start": round(current_day, 1),
                "Late Finish": round(current_day + duration, 1),
                "Float": 0,
                "Critical": "NO",
                "Predecessors": f"A{activity_id-1:03d}",
                "Standard": standard,
                "Confidence": "HIGH" if "ACI" in standard else "LOW"
            })
            current_day += duration
            activity_id += 1
        
        # Per-floor activities (sequential)
        for floor_num in range(1, floors + 1):
            floor_start = current_day
            is_critical = floor_num >= 3  # Critical path typically starts around floor 3
            
            # Floor N Walls (combined wall work)
            schedule.append({
                "ID": f"A{activity_id:03d}",
                "Activity": f"Floor {floor_num} Walls",
                "Floor": floor_num,
                "Duration": round(wall_days, 1),
                "Early Start": round(current_day, 1),
                "Early Finish": round(current_day + wall_days, 1),
                "Late Start": round(current_day, 1),
                "Late Finish": round(current_day + wall_days, 1),
                "Float": 0,
                "Critical": "YES" if is_critical else "NO",
                "Predecessors": f"A{activity_id-1:03d}",
                "Standard": "ACI 347-04, Productivity",
                "Confidence": "LOW"
            })
            current_day += wall_days
            activity_id += 1
            
            # Floor N Slab Formwork
            schedule.append({
                "ID": f"A{activity_id:03d}",
                "Activity": f"Floor {floor_num} Slab Formwork",
                "Floor": floor_num,
                "Duration": round(slab_formwork_days, 1),
                "Early Start": round(current_day, 1),
                "Early Finish": round(current_day + slab_formwork_days, 1),
                "Late Start": round(current_day, 1),
                "Late Finish": round(current_day + slab_formwork_days, 1),
                "Float": 0,
                "Critical": "YES" if is_critical else "NO",
                "Predecessors": f"A{activity_id-1:03d}",
                "Standard": "Productivity",
                "Confidence": "LOW"
            })
            current_day += slab_formwork_days
            activity_id += 1
            
            # Floor N Slab Rebar
            schedule.append({
                "ID": f"A{activity_id:03d}",
                "Activity": f"Floor {floor_num} Slab Rebar",
                "Floor": floor_num,
                "Duration": round(slab_rebar_days, 1),
                "Early Start": round(current_day, 1),
                "Early Finish": round(current_day + slab_rebar_days, 1),
                "Late Start": round(current_day, 1),
                "Late Finish": round(current_day + slab_rebar_days, 1),
                "Float": 0,
                "Critical": "YES" if is_critical else "NO",
                "Predecessors": f"A{activity_id-1:03d}",
                "Standard": "Productivity",
                "Confidence": "LOW"
            })
            current_day += slab_rebar_days
            activity_id += 1
            
            # Floor N Pour
            schedule.append({
                "ID": f"A{activity_id:03d}",
                "Activity": f"Floor {floor_num} Pour",
                "Floor": floor_num,
                "Duration": round(slab_pour_days, 1),
                "Early Start": round(current_day, 1),
                "Early Finish": round(current_day + slab_pour_days, 1),
                "Late Start": round(current_day, 1),
                "Late Finish": round(current_day + slab_pour_days, 1),
                "Float": 0,
                "Critical": "YES" if is_critical else "NO",
                "Predecessors": f"A{activity_id-1:03d}",
                "Standard": "Productivity",
                "Confidence": "LOW"
            })
            current_day += slab_pour_days
            activity_id += 1
            
            # Floor N Curing (HIGH confidence - ACI 347-04)
            schedule.append({
                "ID": f"A{activity_id:03d}",
                "Activity": f"Floor {floor_num} Curing",
                "Floor": floor_num,
                "Duration": curing_days,
                "Early Start": round(current_day, 1),
                "Early Finish": round(current_day + curing_days, 1),
                "Late Start": round(current_day, 1),
                "Late Finish": round(current_day + curing_days, 1),
                "Float": 0,
                "Critical": "YES" if is_critical else "NO",
                "Predecessors": f"A{activity_id-1:03d}",
                "Standard": "ACI 347-04 Sec 3.7.2.3",
                "Confidence": "HIGH"
            })
            current_day += curing_days
            activity_id += 1
        
        total_duration = current_day
        
        # Calculate per-floor cycle time
        floor_cycle = wall_days + slab_formwork_days + slab_rebar_days + slab_pour_days + curing_days
        
        return {
            "building_type": "shear_wall",
            "floors": floors,
            "total_activities": len(schedule),
            "total_duration_days": round(total_duration, 1),
            "floor_cycle_days": round(floor_cycle, 1),
            "schedule": schedule,
            "breakdown_per_floor": {
                "wall_work_days": round(wall_days, 1),
                "slab_formwork_days": round(slab_formwork_days, 1),
                "slab_rebar_days": round(slab_rebar_days, 1),
                "slab_pour_days": round(slab_pour_days, 1),
                "curing_days": curing_days,
                "total_per_floor": round(floor_cycle, 1)
            },
            "standards_applied": {
                "ACI_347-04": "Form removal / curing times (HIGH confidence)",
                "Productivity": "Work duration estimates (LOW confidence)"
            },
            "notes": [
                "Shear wall building - NO BEAMS in schedule",
                "Floors are STRICTLY SEQUENTIAL per ACI 347-04",
                f"Minimum {curing_days} days curing per floor before next floor starts",
                "Productivity estimates have LOW confidence - adjust based on site conditions"
            ]
        }
    
    # ==================== Construction Productivity Queries ====================
    
    def get_productivity_rate(self, category: str, task: str) -> Dict[str, Any]:
        """
        Get construction productivity rates
        
        NOTE: productivity_standards.json is NOT an international standard
        Results should be marked with lower confidence
        
        Args:
            category: 'excavation', 'concrete', 'rebar', 'masonry', 'plaster', 'road'
            task: Specific task name
        
        Returns:
            Dict with productivity data (includes confidence indicator)
        """
        data = self._cache.get('productivity_standards', {})
        productivity_data = data.get('productivity_data', {})
        
        category_map = {
            "excavation": "excavation_earthwork",
            "concrete": "concrete_works",
            "rebar": "reinforcement_work",
            "masonry": "masonry",
            "plaster": "plastering_finishing",
            "road": "road_paving"
        }
        
        cat_key = category_map.get(category.lower(), category)
        
        result = {}
        if cat_key in productivity_data:
            tasks = productivity_data[cat_key].get('tasks', {})
            result = tasks.get(task, {})
        
        # Add confidence indicator - NOT an international standard
        if result:
            result["confidence"] = "LOW"
            result["confidence_note"] = "productivity_standards.json is NOT an international standard - use as estimate only"
        
        return result
    
    def calculate_labor_duration(self, task: str, quantity: float, 
                                 crew_size: int = 1, unit: str = "m3") -> Dict[str, Any]:
        """
        Calculate labor duration for a task
        
        NOTE: Results based on productivity_standards.json have LOW confidence
        
        Args:
            task: Task name (e.g., 'manual_laying', 'fixing_slabs_footings')
            quantity: Quantity of work
            crew_size: Number of workers
            unit: Unit of measurement
        
        Returns:
            Dict with duration calculation (includes confidence indicator)
        """
        data = self._cache.get('productivity_standards', {})
        productivity_data = data.get('productivity_data', {})
        
        # Find task in productivity data
        for category_data in productivity_data.values():
            if "tasks" in category_data:
                if task in category_data["tasks"]:
                    task_data = category_data["tasks"][task]
                    prod = task_data.get("productivity", {})
                    
                    # Get average productivity
                    if "min" in prod and "max" in prod:
                        avg_prod = (prod["min"] + prod["max"]) / 2
                    elif "average" in prod:
                        avg_prod = prod["average"]
                    else:
                        return {"error": "No productivity data available", "confidence": "LOW"}
                    
                    # Calculate duration
                    if "labour-day" in prod.get("unit", ""):
                        total_days = quantity / avg_prod
                        duration_days = total_days / crew_size
                    elif "hour" in prod.get("unit", ""):
                        total_hours = quantity / avg_prod
                        duration_days = (total_hours / 8) / crew_size
                    else:
                        return {"error": "Unknown unit", "confidence": "LOW"}
                    
                    return {
                        "quantity": quantity,
                        "unit": unit,
                        "productivity_avg": avg_prod,
                        "productivity_unit": prod.get("unit"),
                        "crew_size": crew_size,
                        "duration_days": round(duration_days, 2),
                        "task": task,
                        "confidence": "LOW",
                        "confidence_note": "Based on productivity_standards.json - NOT an international standard"
                    }
        
        return {"error": f"Task '{task}' not found", "confidence": "LOW"}
    
    def list_productivity_categories(self) -> List[str]:
        """List all available productivity categories"""
        data = self._cache.get('productivity_standards', {})
        productivity_data = data.get('productivity_data', {})
        return list(productivity_data.keys())
    
    def list_category_tasks(self, category: str) -> List[str]:
        """List all tasks in a category"""
        data = self._cache.get('productivity_standards', {})
        productivity_data = data.get('productivity_data', {})
        
        category_map = {
            "excavation": "excavation_earthwork",
            "concrete": "concrete_works",
            "rebar": "reinforcement_work",
            "masonry": "masonry",
            "plaster": "plastering_finishing",
            "road": "road_paving"
        }
        
        cat_key = category_map.get(category.lower(), category)
        
        if cat_key in productivity_data and "tasks" in productivity_data[cat_key]:
            return list(productivity_data[cat_key]["tasks"].keys())
        
        return []
    
    def estimate_concrete_slab_construction(self, area_m2: float, thickness_mm: float,
                                           crew_size: int = 6) -> Dict[str, Any]:
        """
        Estimate concrete slab construction using productivity standards
        
        NOTE: Results have LOW confidence - based on non-international standard
        
        Args:
            area_m2: Slab area in square meters
            thickness_mm: Slab thickness in millimeters
            crew_size: Size of crew
        
        Returns:
            Complete construction estimate with confidence indicators
        """
        thickness_m = thickness_mm / 1000
        volume_m3 = area_m2 * thickness_m
        rebar_density = 100  # kg/m3
        total_rebar_kg = volume_m3 * rebar_density
        
        # Rebar fixing
        rebar_task = self.calculate_labor_duration("fixing_slabs_footings", 
                                                   total_rebar_kg, crew_size)
        
        # Concrete placement (manual)
        concrete_task = self.calculate_labor_duration("manual_laying",
                                                      volume_m3, crew_size)
        
        # Formwork
        formwork_task = self.calculate_labor_duration("shuttering",
                                                      area_m2, crew_size)
        
        return {
            "slab_dimensions": {
                "area_m2": area_m2,
                "thickness_mm": thickness_mm,
                "volume_m3": volume_m3
            },
            "rebar": {
                "total_kg": total_rebar_kg,
                **rebar_task
            },
            "concrete": concrete_task,
            "formwork": formwork_task,
            "total_duration_estimate_days": sum([
                rebar_task.get("duration_days", 0),
                concrete_task.get("duration_days", 0),
                formwork_task.get("duration_days", 0)
            ]),
            "confidence": "LOW",
            "confidence_note": "Productivity estimates based on non-international standard"
        }
    
    # ==================== Load Combination Queries ====================
    
    def get_load_combinations(self, standard: str = 'ASCE_7_22', 
                             design_method: str = 'LRFD') -> List[Dict]:
        """
        Get load combinations
        
        Args:
            standard: 'ASCE_7_22' (default)
            design_method: 'LRFD' or 'ASD'
        
        Returns:
            List of load combination dictionaries
        """
        if standard == 'ASCE_7_22':
            data = self._cache.get('asce_7_22_combinations', {})
            combos = data.get('load_combinations', {})
            
            if design_method.upper() == 'LRFD':
                return combos.get('strength_design_LRFD', [])
            elif design_method.upper() == 'ASD':
                return combos.get('allowable_stress_design_ASD', [])
        
        return []
    
    def get_load_combination_by_id(self, combo_id: str, standard: str = 'ASCE_7_22') -> Optional[Dict]:
        """Get specific load combination by ID"""
        all_combos = self.get_load_combinations(standard, 'LRFD') + \
                     self.get_load_combinations(standard, 'ASD')
        
        for combo in all_combos:
            if combo.get('id') == combo_id:
                return combo
        return None
    
    # ==================== IFC4 Mapping Queries ====================
    
    def map_layer_to_ifc4(self, layer_name: str) -> Optional[Dict]:
        """
        Map AutoCAD layer name to IFC4 class
        
        Args:
            layer_name: Layer name (e.g., 'S-COLS', 'S-BEAM')
        
        Returns:
            Dict with IFC class, predefined type, structural type
        """
        data = self._cache.get('ifc4_mappings', {})
        mappings = data.get('layer_to_ifc_mappings', {})
        return mappings.get(layer_name)
    
    def map_entity_to_ifc4(self, entity_type: str, geometry_properties: Dict) -> Optional[Dict]:
        """
        Map CAD entity type to IFC4 class based on geometry
        
        Args:
            entity_type: 'LINE', '3DFACE', 'POLYLINE', etc.
            geometry_properties: Dict with geometric properties
        
        Returns:
            Dict with IFC mapping
        """
        data = self._cache.get('ifc4_mappings', {})
        mappings = data.get('entity_type_mappings', {})
        
        entity_mappings = mappings.get(entity_type, {})
        
        # Simple matching - could be enhanced with geometry checks
        for variant, mapping in entity_mappings.items():
            # For now, return first match
            return mapping
        
        return None
    
    def get_ifc4_property_set(self, ifc_class: str) -> Optional[Dict]:
        """Get IFC4 property set for a class"""
        data = self._cache.get('ifc4_mappings', {})
        prop_mappings = data.get('property_mappings', {})
        return prop_mappings.get(ifc_class)
    
    def map_to_etabs_format(self, layer_name: str) -> Optional[Dict]:
        """Get ETABS format mapping for a layer"""
        mapping = self.map_layer_to_ifc4(layer_name)
        if mapping:
            return {
                'etabs_type': mapping.get('etabs_type'),
                'structural_type': mapping.get('structural_type'),
                'ifc_class': mapping.get('ifc_class')
            }
        return None
    
    # ==================== Construction Sequence Queries ====================
    
    def get_construction_sequence(self, building_type: str, 
                                  standard: str = 'RSMeans_2024') -> Optional[Dict]:
        """
        Get standard construction sequence for building type
        
        Args:
            building_type: 'concrete_frame', 'steel_frame', 'shear_wall'
            standard: 'RSMeans_2024' (default)
        
        Returns:
            Dict with sequence activities and productivity rates
        """
        data = self._cache.get('construction_sequences', {})
        building_types = data.get('building_types', {})
        return building_types.get(building_type)
    
    def get_crew_composition(self, crew_type: str) -> Optional[Dict]:
        """Get standard crew composition"""
        data = self._cache.get('construction_sequences', {})
        crews = data.get('crew_compositions', {})
        return crews.get(crew_type)
    
    def calculate_activity_duration(self, activity: Dict, building_data: Dict) -> float:
        """
        Calculate activity duration based on formula and building data
        
        Args:
            activity: Activity dict with duration_formula
            building_data: Dict with building quantities
        
        Returns:
            Duration in days
        """
        formula = activity.get('duration_formula', '')
        
        try:
            # Simple eval - in production, use safer parsing
            # Replace variable names with building_data values
            for key, value in building_data.items():
                formula = formula.replace(key, str(value))
            
            duration = eval(formula)
            return max(0.5, duration)  # Minimum 0.5 days
        except:
            return 1.0  # Default 1 day
    
    # ==================== Utility Methods ====================
    
    def get_standard_info(self, standard_name: str) -> Optional[Dict]:
        """Get information about a standard"""
        standard_map = {
            'ACI_318': 'aci_318_concrete',
            'ACI_318_COMPLETE': 'aci_318_complete',
            'ACI_347': 'aci_347_formwork',
            'AISC_360': 'aisc_360_steel',
            'ASCE_7_22': 'asce_7_22_combinations',
            'IFC4': 'ifc4_mappings',
            'RSMeans': 'construction_sequences',
            'PRODUCTIVITY': 'productivity_standards'
        }
        
        cache_key = standard_map.get(standard_name)
        if cache_key and cache_key in self._cache:
            data = self._cache[cache_key]
            return {
                'standard': data.get('standard'),
                'standard_name': data.get('standard_name'),
                'version': data.get('version'),
                'organization': data.get('organization')
            }
        
        return None
    
    def list_available_standards(self) -> List[str]:
        """List all available standards"""
        return [
            'ACI_318',
            'ACI_318_COMPLETE',
            'ACI_347',
            'AISC_360',
            'ASCE_7_22',
            'IFC4',
            'RSMeans_2024',
            'PRODUCTIVITY'
        ]
    
    def validate_standard_combination(self, material_standard: str, 
                                     load_standard: str) -> bool:
        """Check if standard combination is valid"""
        # Common US combinations
        valid_combinations = [
            ('ACI_318', 'ASCE_7_22'),
            ('AISC_360', 'ASCE_7_22'),
        ]
        
        return (material_standard, load_standard) in valid_combinations


# Singleton instance
_standards_manager_instance = None

def get_standards_manager() -> StandardsManager:
    """Get or create singleton instance"""
    global _standards_manager_instance
    if _standards_manager_instance is None:
        _standards_manager_instance = StandardsManager()
    return _standards_manager_instance
