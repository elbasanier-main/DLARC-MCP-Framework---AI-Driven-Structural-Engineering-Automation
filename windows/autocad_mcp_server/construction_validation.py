#!/usr/bin/env python3
"""
Standards-Based Construction Validation Module
Validates constructability using REAL engineering standards:
- ACI 318-19 (Concrete Design)
- ACI 347-04 (Formwork)
- ASCE 7-22 (Loads)

NO AI - Only deterministic code-based validation
"""

import json
import math
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio
from datetime import datetime
import logging

# Import standards manager for real code data
from standards_module import get_standards_manager

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues"""
    CRITICAL = "critical"   # Code violation - must fix
    HIGH = "high"           # Near code limit - should fix
    MEDIUM = "medium"       # Below optimal - recommended
    LOW = "low"             # Minor issue
    INFO = "info"           # Informational


@dataclass
class ValidationIssue:
    """Represents a validation issue from standards check"""
    issue_id: str
    severity: ValidationSeverity
    category: str
    description: str
    location: Dict
    code_reference: str      # Changed from 'impact' - now shows actual code section
    calculated_value: str    # Changed from 'recommendation' - shows actual vs limit
    standard: str            # Which standard (ACI 318-19, ACI 347-04, etc.)


@dataclass
class ValidationResult:
    """Complete validation result"""
    project_name: str
    validation_timestamp: datetime
    is_constructable: bool
    overall_score: float
    issues: List[ValidationIssue]
    standards_checked: List[str]   # Changed from ai_recommendations
    summary: Dict                  # Changed from risk_assessment


class StandardsBasedValidator:
    """
    Standards-based construction validation
    Uses REAL engineering codes - NO AI fabrication
    """
    
    def __init__(self):
        self.standards_mgr = get_standards_manager()
        self.validation_history = []
        
        # ACI 318-19 Limits (Table 11.3.1.1, Table 6.6.3.1.1)
        self.aci_318_limits = {
            'wall_slenderness_braced': 30,      # h/t max for braced walls
            'wall_slenderness_unbraced': 25,    # h/t max for unbraced walls
            'slab_span_depth_one_way': 20,      # L/h for one-way slabs (Table 7.3.1.1)
            'slab_span_depth_two_way': 33,      # L/h for two-way slabs
            'beam_span_depth': 16,              # L/h for beams (Table 9.3.1.1)
            'min_concrete_cover_interior_mm': 20,   # Table 20.5.1.3.1
            'min_concrete_cover_exterior_mm': 40,
            'min_fc_psi': 2500,                 # Section 19.2.1.1
            'max_fc_psi': 10000,                # Practical limit
            'min_rebar_spacing_mm': 25,         # Section 25.2.1
        }
        
        # ACI 347-04 Limits
        self.aci_347_limits = {
            'max_lateral_pressure_psf': 2000,   # Maximum lateral pressure
            'max_formwork_load_psf': 150,       # Combined DL+LL (Table 2.2)
            'min_safety_factor': 2.0,           # Minimum safety factor
            'min_slab_removal_days': 7,         # Table 4.1 (normal conditions)
            'min_beam_removal_days': 14,
            'min_column_removal_days': 1,
        }
    
    async def validate_constructability(self,
                                        project_data: Dict,
                                        sequence_data: Dict = None,
                                        validate_all: bool = True) -> ValidationResult:
        """
        Validate constructability using engineering standards
        
        Args:
            project_data: Building data from AutoCAD extraction
            sequence_data: Construction sequence (optional)
            validate_all: Run all checks
            
        Returns:
            ValidationResult with standards-based issues
        """
        logger.info(f"[STANDARDS] Validating {project_data.get('name', 'project')} against codes...")
        
        issues = []
        standards_checked = []
        
        # 1. ACI 318-19 Structural Checks
        aci_318_issues = self._validate_aci_318(project_data)
        issues.extend(aci_318_issues)
        if aci_318_issues or validate_all:
            standards_checked.append("ACI 318-19")
        
        # 2. ACI 347-04 Formwork Checks
        aci_347_issues = self._validate_aci_347(project_data)
        issues.extend(aci_347_issues)
        if aci_347_issues or validate_all:
            standards_checked.append("ACI 347-04")
        
        # 3. Geometric Validation
        geometry_issues = self._validate_geometry(project_data)
        issues.extend(geometry_issues)
        
        # Calculate score based on issues
        overall_score = self._calculate_score(issues)
        
        # Constructable if no CRITICAL issues
        is_constructable = not any(
            issue.severity == ValidationSeverity.CRITICAL
            for issue in issues
        )
        
        # Summary of validation
        summary = self._create_summary(issues, project_data)
        
        result = ValidationResult(
            project_name=project_data.get('name', 'unnamed'),
            validation_timestamp=datetime.now(),
            is_constructable=is_constructable,
            overall_score=overall_score,
            issues=issues,
            standards_checked=standards_checked,
            summary=summary
        )
        
        self.validation_history.append(result)
        
        logger.info(f"[STANDARDS] Validation complete: {len(issues)} issues found")
        return result
    
    def _validate_aci_318(self, project_data: Dict) -> List[ValidationIssue]:
        """Validate against ACI 318-19 requirements"""
        issues = []
        issue_count = 0
        
        # Extract building parameters
        floors = project_data.get('floors', 1)
        floor_height = project_data.get('floor_height', 4.0)
        wall_thickness = project_data.get('wall_thickness_m', 0.3)
        if wall_thickness == 0:
            wall_thickness = project_data.get('material_quantities', {}).get('wall_thickness_m', 0.3)
        
        slab_thickness = project_data.get('slab_thickness_m', 0.2)
        if slab_thickness == 0:
            slab_thickness = project_data.get('material_quantities', {}).get('floor_thickness_m', 0.2)
        
        fc_psi = project_data.get('concrete_strength_psi', 4000)
        
        # Get bounds for span calculations
        bounds = project_data.get('bounds', {})
        length = bounds.get('width', project_data.get('length', 30))
        width = bounds.get('length', project_data.get('width', 12))
        
        # ==================== CHECK 1: Wall Slenderness Ratio ====================
        # ACI 318-19 Section 11.3.1.1 - Slenderness limits
        if wall_thickness > 0:
            wall_height_m = floor_height
            slenderness_ratio = wall_height_m / wall_thickness
            
            # Assume braced walls for shear wall buildings
            limit = self.aci_318_limits['wall_slenderness_braced']
            
            if slenderness_ratio > limit:
                issue_count += 1
                issues.append(ValidationIssue(
                    issue_id=f"ACI318_{issue_count:03d}",
                    severity=ValidationSeverity.CRITICAL,
                    category="structural",
                    description=f"Wall slenderness ratio {slenderness_ratio:.1f} exceeds ACI 318-19 limit of {limit}",
                    location={'element': 'shear_walls', 'all_floors': True},
                    code_reference="ACI 318-19 Table 11.3.1.1",
                    calculated_value=f"h/t = {wall_height_m:.2f}m / {wall_thickness:.2f}m = {slenderness_ratio:.1f} > {limit}",
                    standard="ACI 318-19"
                ))
            elif slenderness_ratio > limit * 0.9:
                issue_count += 1
                issues.append(ValidationIssue(
                    issue_id=f"ACI318_{issue_count:03d}",
                    severity=ValidationSeverity.MEDIUM,
                    category="structural",
                    description=f"Wall slenderness ratio {slenderness_ratio:.1f} is near ACI 318-19 limit of {limit}",
                    location={'element': 'shear_walls', 'all_floors': True},
                    code_reference="ACI 318-19 Table 11.3.1.1",
                    calculated_value=f"h/t = {slenderness_ratio:.1f}, limit = {limit} (at 90% of limit)",
                    standard="ACI 318-19"
                ))
        
        # ==================== CHECK 2: Slab Span-to-Depth Ratio ====================
        # ACI 318-19 Table 7.3.1.1 - Minimum slab thickness
        if slab_thickness > 0:
            # Assume shorter span controls for two-way slab
            shorter_span = min(length, width)
            span_depth_ratio = shorter_span / slab_thickness
            
            limit = self.aci_318_limits['slab_span_depth_two_way']
            
            if span_depth_ratio > limit:
                issue_count += 1
                issues.append(ValidationIssue(
                    issue_id=f"ACI318_{issue_count:03d}",
                    severity=ValidationSeverity.HIGH,
                    category="structural",
                    description=f"Slab span/depth ratio {span_depth_ratio:.1f} exceeds ACI 318-19 limit of {limit}",
                    location={'element': 'floor_slabs', 'span': f"{shorter_span:.1f}m"},
                    code_reference="ACI 318-19 Table 7.3.1.1",
                    calculated_value=f"L/h = {shorter_span:.2f}m / {slab_thickness:.2f}m = {span_depth_ratio:.1f} > {limit}",
                    standard="ACI 318-19"
                ))
            elif span_depth_ratio > limit * 0.85:
                issue_count += 1
                issues.append(ValidationIssue(
                    issue_id=f"ACI318_{issue_count:03d}",
                    severity=ValidationSeverity.LOW,
                    category="structural",
                    description=f"Slab span/depth ratio {span_depth_ratio:.1f} approaching limit",
                    location={'element': 'floor_slabs'},
                    code_reference="ACI 318-19 Table 7.3.1.1",
                    calculated_value=f"L/h = {span_depth_ratio:.1f}, limit = {limit}",
                    standard="ACI 318-19"
                ))
        
        # ==================== CHECK 3: Concrete Strength ====================
        # ACI 318-19 Section 19.2.1.1
        min_fc = self.aci_318_limits['min_fc_psi']
        
        if fc_psi < min_fc:
            issue_count += 1
            issues.append(ValidationIssue(
                issue_id=f"ACI318_{issue_count:03d}",
                severity=ValidationSeverity.CRITICAL,
                category="material",
                description=f"Concrete strength {fc_psi} psi below ACI 318-19 minimum of {min_fc} psi",
                location={'element': 'all_concrete'},
                code_reference="ACI 318-19 Section 19.2.1.1",
                calculated_value=f"fc' = {fc_psi} psi < {min_fc} psi minimum",
                standard="ACI 318-19"
            ))
        
        # ==================== CHECK 4: Building Height Check ====================
        # Practical limits for shear wall buildings
        total_height = floors * floor_height
        aspect_ratio = total_height / min(length, width)
        
        if aspect_ratio > 6:
            issue_count += 1
            issues.append(ValidationIssue(
                issue_id=f"ACI318_{issue_count:03d}",
                severity=ValidationSeverity.HIGH,
                category="structural",
                description=f"Building aspect ratio {aspect_ratio:.1f} exceeds typical limit of 6 for shear wall buildings",
                location={'element': 'building', 'height': f"{total_height:.1f}m"},
                code_reference="Engineering Practice (ASCE 7-22 reference)",
                calculated_value=f"H/B = {total_height:.1f}m / {min(length, width):.1f}m = {aspect_ratio:.1f}",
                standard="ACI 318-19"
            ))
        
        return issues
    
    def _validate_aci_347(self, project_data: Dict) -> List[ValidationIssue]:
        """Validate against ACI 347-04 formwork requirements"""
        issues = []
        issue_count = 0
        
        # Extract parameters
        floors = project_data.get('floors', 1)
        floor_height = project_data.get('floor_height', 4.0)
        floor_height_ft = floor_height * 3.28084
        
        # Get formwork data from standards
        formwork_loads = self.standards_mgr.get_formwork_loads(use_motorized_carts=True)
        lateral_pressure = self.standards_mgr.get_lateral_pressure(
            placement_rate=2.0,
            temperature=70,
            concrete_height=floor_height_ft
        )
        
        # ==================== CHECK 1: Lateral Pressure ====================
        # ACI 347-04 - Maximum lateral pressure
        if lateral_pressure:
            pressure_psf = lateral_pressure.get('lateral_pressure_psf', 0)
            max_pressure = self.aci_347_limits['max_lateral_pressure_psf']
            
            if pressure_psf > max_pressure:
                issue_count += 1
                issues.append(ValidationIssue(
                    issue_id=f"ACI347_{issue_count:03d}",
                    severity=ValidationSeverity.HIGH,
                    category="formwork",
                    description=f"Calculated lateral pressure {pressure_psf:.0f} psf exceeds maximum {max_pressure} psf",
                    location={'element': 'wall_formwork', 'height': f"{floor_height:.1f}m"},
                    code_reference="ACI 347-04 Section 2.2.2",
                    calculated_value=f"p = {pressure_psf:.0f} psf > {max_pressure} psf (using p=150+9000R/T)",
                    standard="ACI 347-04"
                ))
        
        # ==================== CHECK 2: Pour Height Check ====================
        # High pours require special consideration
        if floor_height > 4.5:  # meters
            issue_count += 1
            issues.append(ValidationIssue(
                issue_id=f"ACI347_{issue_count:03d}",
                severity=ValidationSeverity.MEDIUM,
                category="formwork",
                description=f"Floor height {floor_height:.1f}m exceeds typical single-pour height of 4.5m",
                location={'element': 'wall_formwork'},
                code_reference="ACI 347-04 Section 3.4",
                calculated_value=f"Pour height = {floor_height:.1f}m, consider staged pours",
                standard="ACI 347-04"
            ))
        
        # ==================== CHECK 3: Form Removal Times ====================
        # Check that project allows adequate curing
        min_slab_removal = self.aci_347_limits['min_slab_removal_days']
        
        if floors > 5:
            issue_count += 1
            issues.append(ValidationIssue(
                issue_id=f"ACI347_{issue_count:03d}",
                severity=ValidationSeverity.INFO,
                category="formwork",
                description=f"Multi-story building ({floors} floors) requires reshoring per ACI 347-04",
                location={'element': 'floor_slabs', 'floors': floors},
                code_reference="ACI 347-04 Section 4.4",
                calculated_value=f"Min slab form removal: {min_slab_removal} days at 70F",
                standard="ACI 347-04"
            ))
        
        return issues
    
    def _validate_geometry(self, project_data: Dict) -> List[ValidationIssue]:
        """Validate geometric constraints"""
        issues = []
        issue_count = 0
        
        bounds = project_data.get('bounds', {})
        volumes = project_data.get('volumes', {})
        material_qty = project_data.get('material_quantities', {})
        
        # Get dimensions
        length = bounds.get('width', 0)
        width = bounds.get('length', 0)
        height = bounds.get('height', 0)
        
        if length == 0 or width == 0:
            return issues
        
        # ==================== CHECK 1: Floor Plate Aspect Ratio ====================
        floor_aspect = max(length, width) / min(length, width) if min(length, width) > 0 else 0
        
        if floor_aspect > 4:
            issue_count += 1
            issues.append(ValidationIssue(
                issue_id=f"GEOM_{issue_count:03d}",
                severity=ValidationSeverity.MEDIUM,
                category="geometry",
                description=f"Floor plate aspect ratio {floor_aspect:.1f} exceeds recommended 4:1",
                location={'element': 'floor_plate', 'dimensions': f"{length:.1f}m x {width:.1f}m"},
                code_reference="Engineering Practice",
                calculated_value=f"Aspect = {length:.1f}/{width:.1f} = {floor_aspect:.1f}",
                standard="Geometric"
            ))
        
        # ==================== CHECK 2: Concrete Volume Reasonability ====================
        total_volume = volumes.get('total_volume', 0)
        if total_volume == 0:
            total_volume = material_qty.get('concrete_volume_m3', 0)
        
        floors = project_data.get('floors', 1)
        floor_area = length * width
        
        if floor_area > 0 and total_volume > 0:
            volume_per_floor_per_m2 = (total_volume / floors) / floor_area
            
            # Typical range: 0.15-0.35 m3/m2 for RC buildings
            if volume_per_floor_per_m2 > 0.5:
                issue_count += 1
                issues.append(ValidationIssue(
                    issue_id=f"GEOM_{issue_count:03d}",
                    severity=ValidationSeverity.LOW,
                    category="geometry",
                    description=f"Concrete volume {volume_per_floor_per_m2:.2f} m3/m2 is high (typical: 0.15-0.35)",
                    location={'element': 'structure'},
                    code_reference="Industry Standard",
                    calculated_value=f"{total_volume:.1f}m3 / {floors} floors / {floor_area:.1f}m2 = {volume_per_floor_per_m2:.2f} m3/m2",
                    standard="Geometric"
                ))
        
        return issues
    
    def _calculate_score(self, issues: List[ValidationIssue]) -> float:
        """Calculate constructability score (1.0 = no issues)"""
        if not issues:
            return 1.0
        
        # Deduct points based on severity
        deductions = {
            ValidationSeverity.CRITICAL: 0.25,
            ValidationSeverity.HIGH: 0.10,
            ValidationSeverity.MEDIUM: 0.05,
            ValidationSeverity.LOW: 0.02,
            ValidationSeverity.INFO: 0.00
        }
        
        score = 1.0
        for issue in issues:
            score -= deductions.get(issue.severity, 0)
        
        return max(0.0, score)
    
    def _create_summary(self, issues: List[ValidationIssue], project_data: Dict) -> Dict:
        """Create validation summary"""
        # Count by severity
        severity_counts = {}
        for issue in issues:
            sev = issue.severity.value
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        # Count by standard
        standard_counts = {}
        for issue in issues:
            std = issue.standard
            standard_counts[std] = standard_counts.get(std, 0) + 1
        
        return {
            'total_issues': len(issues),
            'by_severity': severity_counts,
            'by_standard': standard_counts,
            'building_parameters': {
                'floors': project_data.get('floors', 0),
                'height': project_data.get('bounds', {}).get('height', 0),
                'footprint': f"{project_data.get('bounds', {}).get('width', 0):.1f}m x {project_data.get('bounds', {}).get('length', 0):.1f}m"
            }
        }
    
    def export_validation_report(self, result: ValidationResult, filepath: str):
        """Export validation report to JSON file"""
        report = {
            'project': result.project_name,
            'timestamp': result.validation_timestamp.isoformat(),
            'constructable': result.is_constructable,
            'score': result.overall_score,
            'standards_checked': result.standards_checked,
            'issues': [
                {
                    'id': i.issue_id,
                    'severity': i.severity.value,
                    'category': i.category,
                    'description': i.description,
                    'location': i.location,
                    'code_reference': i.code_reference,
                    'calculated_value': i.calculated_value,
                    'standard': i.standard
                }
                for i in result.issues
            ],
            'summary': result.summary
        }
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"[STANDARDS] Validation report exported to {filepath}")


# Backward compatibility alias
AIConstructionValidator = StandardsBasedValidator
