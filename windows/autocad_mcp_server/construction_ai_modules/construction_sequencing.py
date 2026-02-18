#!/usr/bin/env python3
"""
AI-Powered Construction Sequencing Module
Generates optimal construction sequences using pattern learning and LLM integration
"""

import json
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ConstructionPhase(Enum):
    """Construction phases for sequencing"""
    SITE_PREPARATION = "site_preparation"
    FOUNDATION = "foundation"
    SUBSTRUCTURE = "substructure"
    SUPERSTRUCTURE = "superstructure"
    ENVELOPE = "envelope"
    INTERIOR = "interior"
    MEP = "mep_systems"
    FINISHES = "finishes"
    COMMISSIONING = "commissioning"

@dataclass
class ConstructionActivity:
    """Represents a construction activity"""
    id: str
    name: str
    phase: ConstructionPhase
    duration_days: float
    predecessors: List[str] = field(default_factory=list)
    resources_required: Dict[str, int] = field(default_factory=dict)
    spatial_zone: str = ""
    floor_level: int = 0
    crew_size: int = 1
    
@dataclass
class ConstructionSequence:
    """AI-generated construction sequence"""
    project_name: str
    activities: List[ConstructionActivity]
    critical_path: List[str]
    total_duration: float
    resource_histogram: Dict[str, List[int]]
    ai_confidence: float
    optimization_score: float
    generated_at: datetime

class AIConstructionSequencer:
    """AI-powered construction sequence generator"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.pattern_database = {}
        self.learning_history = []
        self.optimization_weights = {
            'time': 0.3,
            'cost': 0.25,
            'safety': 0.25,
            'resource_leveling': 0.2
        }
        
    async def generate_sequence(self, 
                               building_data: Dict,
                               constraints: Dict = None,
                               optimization_mode: str = "balanced") -> ConstructionSequence:
        """
        Generate AI-optimized construction sequence
        
        Args:
            building_data: Building geometry and structural data
            constraints: Project constraints (time, resources, etc.)
            optimization_mode: "time", "cost", "safety", or "balanced"
        """
        logger.info(f"Generating construction sequence for {building_data.get('name', 'building')}")
        
        # Extract building features
        features = self._extract_building_features(building_data)
        
        # Use AI to determine construction method
        construction_method = await self._ai_select_method(features)
        
        # Generate base sequence using patterns
        base_sequence = self._generate_base_sequence(features, construction_method)
        
        # Apply AI optimization
        optimized_sequence = await self._ai_optimize_sequence(
            base_sequence, 
            constraints or {},
            optimization_mode
        )
        
        # Calculate critical path
        critical_path = self._calculate_critical_path(optimized_sequence)
        
        # Generate resource histogram
        resource_histogram = self._generate_resource_histogram(optimized_sequence)
        
        # Calculate metrics
        total_duration = self._calculate_total_duration(optimized_sequence, critical_path)
        ai_confidence = self._calculate_confidence(features, len(self.learning_history))
        optimization_score = self._calculate_optimization_score(optimized_sequence)
        
        return ConstructionSequence(
            project_name=building_data.get('name', 'unnamed'),
            activities=optimized_sequence,
            critical_path=critical_path,
            total_duration=total_duration,
            resource_histogram=resource_histogram,
            ai_confidence=ai_confidence,
            optimization_score=optimization_score,
            generated_at=datetime.now()
        )
    
    def _extract_building_features(self, building_data: Dict) -> Dict:
        """Extract relevant features for sequence generation"""
        features = {
            'floors': building_data.get('floors', 1),
            'floor_area': building_data.get('floor_area', 1000),
            'structural_system': building_data.get('structural_system', 'frame'),
            'material': building_data.get('material', 'concrete'),
            'complexity': self._calculate_complexity(building_data),
            'height': building_data.get('height', 3.5 * building_data.get('floors', 1)),
            'has_basement': building_data.get('has_basement', False),
            'special_features': building_data.get('special_features', [])
        }
        return features
    
    def _calculate_complexity(self, building_data: Dict) -> float:
        """Calculate building complexity score"""
        complexity = 0.0
        
        # Floor count complexity
        floors = building_data.get('floors', 1)
        if floors > 50:
            complexity += 0.3
        elif floors > 20:
            complexity += 0.2
        elif floors > 10:
            complexity += 0.1
            
        # Structural system complexity
        system = building_data.get('structural_system', 'frame')
        complexity_map = {
            'frame': 0.1,
            'shear_wall': 0.15,
            'tube': 0.25,
            'composite': 0.3
        }
        complexity += complexity_map.get(system, 0.1)
        
        # Special features
        special_features = building_data.get('special_features', [])
        complexity += len(special_features) * 0.05
        
        return min(complexity, 1.0)
    
    async def _ai_select_method(self, features: Dict) -> str:
        """Use AI to select optimal construction method"""
        if self.llm_client:
            prompt = f"""
            As a construction AI expert, select the optimal construction method for:
            - Floors: {features['floors']}
            - System: {features['structural_system']}
            - Material: {features['material']}
            - Complexity: {features['complexity']:.2f}
            
            Options: top-down, bottom-up, mixed-use, prefab, modular
            Return only the method name.
            """
            
            try:
                response = await self.llm_client.generate(prompt)
                method = response.strip().lower()
                if method in ['top-down', 'bottom-up', 'mixed-use', 'prefab', 'modular']:
                    return method
            except:
                pass
        
        # Fallback to rule-based selection
        if features['floors'] > 30:
            return 'top-down'
        elif features['complexity'] > 0.7:
            return 'mixed-use'
        else:
            return 'bottom-up'
    
    def _generate_base_sequence(self, features: Dict, method: str) -> List[ConstructionActivity]:
        """Generate base construction sequence"""
        activities = []
        activity_id = 1
        
        # Site preparation
        activities.append(ConstructionActivity(
            id=f"A{activity_id:03d}",
            name="Site preparation and setup",
            phase=ConstructionPhase.SITE_PREPARATION,
            duration_days=7,
            crew_size=10
        ))
        activity_id += 1
        
        # Foundation
        if features['has_basement']:
            activities.append(ConstructionActivity(
                id=f"A{activity_id:03d}",
                name="Excavation and shoring",
                phase=ConstructionPhase.FOUNDATION,
                duration_days=14,
                predecessors=[f"A{activity_id-1:03d}"],
                crew_size=8
            ))
            activity_id += 1
        
        activities.append(ConstructionActivity(
            id=f"A{activity_id:03d}",
            name="Foundation construction",
            phase=ConstructionPhase.FOUNDATION,
            duration_days=21,
            predecessors=[f"A{activity_id-1:03d}"],
            crew_size=12
        ))
        activity_id += 1
        
        # Generate floor-by-floor activities based on method
        floors = features['floors']
        
        if method == 'bottom-up':
            for floor in range(1, floors + 1):
                # Structure
                activities.append(ConstructionActivity(
                    id=f"A{activity_id:03d}",
                    name=f"Floor {floor} structure",
                    phase=ConstructionPhase.SUPERSTRUCTURE,
                    duration_days=5,
                    predecessors=[f"A{activity_id-1:03d}"],
                    floor_level=floor,
                    crew_size=15
                ))
                activity_id += 1
                
                # MEP rough-in (starts 2 floors behind structure)
                if floor > 2:
                    activities.append(ConstructionActivity(
                        id=f"A{activity_id:03d}",
                        name=f"Floor {floor-2} MEP rough-in",
                        phase=ConstructionPhase.MEP,
                        duration_days=3,
                        predecessors=[f"A{activity_id-3:03d}"],
                        floor_level=floor-2,
                        crew_size=10
                    ))
                    activity_id += 1
        
        # Envelope
        activities.append(ConstructionActivity(
            id=f"A{activity_id:03d}",
            name="Building envelope",
            phase=ConstructionPhase.ENVELOPE,
            duration_days=30,
            predecessors=[f"A{activity_id-floors:03d}"],
            crew_size=20
        ))
        activity_id += 1
        
        # Finishes
        activities.append(ConstructionActivity(
            id=f"A{activity_id:03d}",
            name="Interior finishes",
            phase=ConstructionPhase.FINISHES,
            duration_days=45,
            predecessors=[f"A{activity_id-1:03d}"],
            crew_size=25
        ))
        
        return activities
    
    async def _ai_optimize_sequence(self, 
                                   activities: List[ConstructionActivity],
                                   constraints: Dict,
                                   mode: str) -> List[ConstructionActivity]:
        """Apply AI optimization to sequence"""
        if self.llm_client:
            # Prepare optimization prompt
            activities_json = [
                {
                    'id': a.id,
                    'name': a.name,
                    'duration': a.duration_days,
                    'predecessors': a.predecessors
                }
                for a in activities
            ]
            
            prompt = f"""
            Optimize this construction sequence for {mode}:
            Activities: {json.dumps(activities_json)}
            Constraints: {json.dumps(constraints)}
            
            Suggest improvements to reduce duration or improve resource usage.
            Return specific modifications as JSON.
            """
            
            try:
                response = await self.llm_client.generate(prompt)
                # Parse and apply optimizations
                # This would include logic to modify activities based on AI suggestions
            except:
                pass
        
        # Apply pattern-based optimizations
        return self._apply_pattern_optimizations(activities, mode)
    
    def _apply_pattern_optimizations(self, 
                                    activities: List[ConstructionActivity],
                                    mode: str) -> List[ConstructionActivity]:
        """Apply learned pattern optimizations"""
        optimized = activities.copy()
        
        if mode == "time":
            # Parallelize activities where possible
            for i, activity in enumerate(optimized):
                if activity.phase == ConstructionPhase.MEP:
                    # MEP can start earlier
                    if activity.floor_level > 1:
                        activity.duration_days *= 0.9
        
        elif mode == "cost":
            # Optimize crew sizes for cost
            for activity in optimized:
                if activity.crew_size > 15:
                    activity.crew_size = int(activity.crew_size * 0.85)
                    activity.duration_days *= 1.1
        
        elif mode == "safety":
            # Add safety buffers
            for activity in optimized:
                if activity.phase in [ConstructionPhase.SUPERSTRUCTURE, ConstructionPhase.ENVELOPE]:
                    activity.duration_days *= 1.15
        
        return optimized
    
    def _calculate_critical_path(self, activities: List[ConstructionActivity]) -> List[str]:
        """Calculate critical path using CPM algorithm"""
        # Build activity network
        network = {}
        for activity in activities:
            network[activity.id] = {
                'duration': activity.duration_days,
                'predecessors': activity.predecessors,
                'early_start': 0,
                'early_finish': 0,
                'late_start': float('inf'),
                'late_finish': float('inf'),
                'slack': 0
            }
        
        # Forward pass
        for activity in activities:
            if not activity.predecessors:
                network[activity.id]['early_start'] = 0
                network[activity.id]['early_finish'] = activity.duration_days
            else:
                max_finish = max([network[pred]['early_finish'] 
                                for pred in activity.predecessors])
                network[activity.id]['early_start'] = max_finish
                network[activity.id]['early_finish'] = max_finish + activity.duration_days
        
        # Find project completion time
        project_duration = max([network[a]['early_finish'] for a in network])
        
        # Backward pass
        for activity in reversed(activities):
            if network[activity.id]['early_finish'] == project_duration:
                network[activity.id]['late_finish'] = project_duration
                network[activity.id]['late_start'] = project_duration - activity.duration_days
            
            for pred_id in activity.predecessors:
                if network[pred_id]['late_finish'] > network[activity.id]['late_start']:
                    network[pred_id]['late_finish'] = network[activity.id]['late_start']
                    network[pred_id]['late_start'] = network[pred_id]['late_finish'] - \
                                                     network[pred_id]['duration']
        
        # Calculate slack and identify critical path
        critical_path = []
        for activity_id, data in network.items():
            data['slack'] = data['late_start'] - data['early_start']
            if data['slack'] == 0:
                critical_path.append(activity_id)
        
        return critical_path
    
    def _generate_resource_histogram(self, activities: List[ConstructionActivity]) -> Dict[str, List[int]]:
        """Generate resource usage histogram"""
        # Find project duration
        max_day = int(max([a.duration_days for a in activities]) * len(activities) * 0.3)
        
        histogram = {
            'workers': [0] * max_day,
            'equipment': [0] * max_day,
            'materials': [0] * max_day
        }
        
        # This is simplified - in practice would use network calculations
        for day in range(max_day):
            # Simulate resource usage
            histogram['workers'][day] = np.random.randint(10, 50)
            histogram['equipment'][day] = np.random.randint(5, 20)
            histogram['materials'][day] = np.random.randint(100, 500)
        
        return histogram
    
    def _calculate_total_duration(self, activities: List[ConstructionActivity], 
                                 critical_path: List[str]) -> float:
        """Calculate total project duration"""
        critical_activities = [a for a in activities if a.id in critical_path]
        return sum([a.duration_days for a in critical_activities])
    
    def _calculate_confidence(self, features: Dict, training_size: int) -> float:
        """Calculate AI confidence score"""
        base_confidence = min(training_size / 1000, 0.5)  # Up to 50% from training
        
        # Adjust based on complexity
        complexity_penalty = features['complexity'] * 0.2
        
        # Adjust based on similar projects
        similarity_bonus = 0.3 if training_size > 100 else 0.0
        
        # Calculate final confidence and clamp between 0 and 0.95
        confidence = base_confidence + similarity_bonus - complexity_penalty
        return max(0.0, min(confidence, 0.95))  # Never negative, never > 95%
    
    def _calculate_optimization_score(self, activities: List[ConstructionActivity]) -> float:
        """Calculate optimization quality score"""
        # Simple scoring based on parallelization and resource leveling
        parallel_activities = 0
        for i, activity in enumerate(activities):
            for j, other in enumerate(activities):
                if i != j and not (activity.id in other.predecessors or 
                                 other.id in activity.predecessors):
                    parallel_activities += 1
        
        parallelization_score = min(parallel_activities / (len(activities) * 2), 1.0)
        
        # Resource leveling score (simplified)
        resource_variance = np.random.random() * 0.3  # Placeholder
        leveling_score = 1.0 - resource_variance
        
        return (parallelization_score + leveling_score) / 2
    
    async def learn_from_execution(self, 
                                  sequence: ConstructionSequence,
                                  actual_results: Dict):
        """Learn from actual execution results"""
        learning_entry = {
            'sequence': sequence,
            'actual': actual_results,
            'timestamp': datetime.now(),
            'variance': self._calculate_variance(sequence, actual_results)
        }
        
        self.learning_history.append(learning_entry)
        
        # Update patterns
        if learning_entry['variance'] < 0.1:  # Good prediction
            self._update_patterns(sequence)
    
    def _calculate_variance(self, sequence: ConstructionSequence, actual: Dict) -> float:
        """Calculate variance between predicted and actual"""
        predicted_duration = sequence.total_duration
        actual_duration = actual.get('duration', predicted_duration)
        
        return abs(predicted_duration - actual_duration) / predicted_duration
    
    def _update_patterns(self, sequence: ConstructionSequence):
        """Update pattern database with successful sequence"""
        key = f"{len(sequence.activities)}_{sequence.project_name[:10]}"
        self.pattern_database[key] = {
            'activities': sequence.activities,
            'duration': sequence.total_duration,
            'score': sequence.optimization_score
        }
    
    def export_sequence_to_json(self, sequence: ConstructionSequence) -> str:
        """Export sequence to JSON format"""
        return json.dumps({
            'project': sequence.project_name,
            'activities': [
                {
                    'id': a.id,
                    'name': a.name,
                    'phase': a.phase.value,
                    'duration': a.duration_days,
                    'predecessors': a.predecessors,
                    'floor': a.floor_level,
                    'crew': a.crew_size
                }
                for a in sequence.activities
            ],
            'critical_path': sequence.critical_path,
            'total_duration': sequence.total_duration,
            'ai_confidence': sequence.ai_confidence,
            'optimization_score': sequence.optimization_score,
            'generated': sequence.generated_at.isoformat()
        }, indent=2)
