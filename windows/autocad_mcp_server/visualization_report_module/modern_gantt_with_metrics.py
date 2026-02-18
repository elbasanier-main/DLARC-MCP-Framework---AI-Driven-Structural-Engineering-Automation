"""
Modern Construction Gantt Chart with Standards Metrics Display
UPDATED: Fixed floor ordering (strictly sequential) and ACI 347-04 based scheduling
Shows real-time standards data: ACI 318 calculations, ACI 347 formwork, productivity rates
NO emojis, clean professional output
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np
from typing import List, Dict, Any, Optional


class ModernConstructionGantt:
    """Modern Gantt with standards metrics panel - FIXED floor ordering"""
    
    # Professional color scheme (Material Design inspired)
    COLORS = {
        'excavation': '#455A64',    # Blue Grey 700
        'foundation': '#546E7A',    # Blue Grey 600
        'concrete': '#1976D2',      # Blue 700
        'formwork': '#42A5F5',      # Blue 400
        'rebar': '#D32F2F',         # Red 700
        'masonry': '#F57C00',       # Orange 700
        'steel': '#616161',         # Grey 700
        'finishes': '#00897B',      # Teal 600
        'mep': '#5E35B1',           # Deep Purple 600
        'site_work': '#388E3C',     # Green 700
        'curing': '#7B1FA2',        # Purple 700
        'default': '#757575'        # Grey 600
    }
    
    def __init__(self, title: str = "Construction Schedule", figsize: tuple = (18, 12)):
        self.title = title
        self.figsize = figsize
        self.fig = None
        self.ax_gantt = None
        self.ax_metrics = None
        
    def create_chart_with_metrics(self, 
                                  tasks: List[Dict[str, Any]],
                                  standards_data: Optional[Dict] = None,
                                  start_date: Optional[datetime] = None) -> plt.Figure:
        """
        Create Gantt chart with standards metrics panel
        
        Args:
            tasks: List of task dictionaries
            standards_data: Dict with ACI 318, ACI 347, productivity data
            start_date: Project start date
        """
        if start_date is None:
            start_date = datetime.now()
        
        # Create figure with GridSpec (70% Gantt, 30% Metrics)
        self.fig = plt.figure(figsize=self.figsize, facecolor='white')
        gs = GridSpec(1, 3, figure=self.fig, wspace=0.3)
        
        # Main Gantt chart area
        self.ax_gantt = self.fig.add_subplot(gs[0, :2])
        
        # Metrics panel
        self.ax_metrics = self.fig.add_subplot(gs[0, 2])
        
        # Process and draw tasks - FIXED: maintain sequential floor order
        processed_tasks = self._process_tasks_sequential(tasks, start_date)
        self._draw_gantt(processed_tasks)
        
        # Draw metrics panel
        if standards_data:
            self._draw_metrics_panel(standards_data, processed_tasks)
        
        # Style
        self._style_chart(processed_tasks)
        
        plt.tight_layout()
        return self.fig
    
    def _process_tasks_sequential(self, tasks: List[Dict], start_date: datetime) -> List[Dict]:
        """
        Process tasks and calculate dates - FIXED to maintain sequential floor order
        
        CRITICAL: Do NOT sort by start_date - maintain logical order:
        1. Pre-construction tasks (site prep, foundation)
        2. Floor tasks in sequential order (Floor 1, Floor 2, ..., Floor N)
        3. Post-construction tasks (finishes, commissioning)
        """
        processed = []
        
        # Group tasks by floor number for proper ordering
        pre_construction = []
        floor_tasks = {}  # {floor_num: [tasks]}
        post_construction = []
        
        for idx, task in enumerate(tasks):
            p_task = task.copy()
            p_task['original_idx'] = idx
            p_task['id'] = task.get('id', idx)
            
            if isinstance(task['start'], datetime):
                p_task['start_date'] = task['start']
            else:
                p_task['start_date'] = start_date + timedelta(days=task['start'])
            
            duration = task.get('duration', 1)
            p_task['end_date'] = p_task['start_date'] + timedelta(days=duration)
            p_task['duration_days'] = duration
            p_task['category'] = task.get('category', 'default')
            p_task['priority'] = task.get('priority', 'medium')
            p_task['progress'] = task.get('progress', 0)
            p_task['standards_metrics'] = task.get('standards_metrics', {})
            
            # Extract floor number from task name or explicit floor field
            floor_num = task.get('floor', None)
            if floor_num is None:
                # Try to extract from name (e.g., "Floor 3 Formwork", "3Floor Concrete")
                name = task.get('name', '')
                floor_num = self._extract_floor_number(name)
            
            p_task['floor_num'] = floor_num
            
            # Categorize task
            name_lower = task.get('name', '').lower()
            if floor_num is not None and floor_num > 0:
                if floor_num not in floor_tasks:
                    floor_tasks[floor_num] = []
                floor_tasks[floor_num].append(p_task)
            elif any(kw in name_lower for kw in ['foundation', 'site', 'excavation', 'mobilization']):
                pre_construction.append(p_task)
            elif any(kw in name_lower for kw in ['finish', 'commission', 'handover', 'punch']):
                post_construction.append(p_task)
            else:
                pre_construction.append(p_task)
        
        # Build final list in correct order
        # 1. Pre-construction (sorted by start date)
        pre_construction.sort(key=lambda x: x['start_date'])
        processed.extend(pre_construction)
        
        # 2. Floor tasks in STRICT sequential order (1, 2, 3, ..., N)
        for floor_num in sorted(floor_tasks.keys()):
            floor_list = floor_tasks[floor_num]
            # Within each floor, sort by start date
            floor_list.sort(key=lambda x: x['start_date'])
            processed.extend(floor_list)
        
        # 3. Post-construction (sorted by start date)
        post_construction.sort(key=lambda x: x['start_date'])
        processed.extend(post_construction)
        
        return processed
    
    def _extract_floor_number(self, name: str) -> Optional[int]:
        """Extract floor number from task name"""
        import re
        
        # Pattern: "Floor X", "X Floor", "Floor_X", "FloorX", etc.
        patterns = [
            r'[Ff]loor[\s_-]*(\d+)',  # Floor 3, Floor_3, Floor-3
            r'(\d+)[\s_-]*[Ff]loor',  # 3 Floor, 3Floor, 3_Floor
            r'[Ff](\d+)',              # F3
            r'[Ll]evel[\s_-]*(\d+)',  # Level 3
        ]
        
        for pattern in patterns:
            match = re.search(pattern, name)
            if match:
                return int(match.group(1))
        
        return None
    
    def _draw_gantt(self, tasks: List[Dict]):
        """Draw Gantt chart bars"""
        for idx, task in enumerate(tasks):
            y_pos = len(tasks) - idx - 1
            start = task['start_date']
            end = task['end_date']
            duration = (end - start).days
            if duration < 1:
                duration = 1  # Minimum 1 day for display
            
            category = task['category'].lower()
            color = self.COLORS.get(category, self.COLORS['default'])
            
            # Main bar
            bar_height = 0.7
            self.ax_gantt.barh(y_pos, duration, left=start, height=bar_height,
                              color=color, alpha=0.85, edgecolor='white',
                              linewidth=1.5, zorder=2)
            
            # Progress overlay
            if task['progress'] > 0:
                progress_duration = duration * (task['progress'] / 100)
                self.ax_gantt.barh(y_pos, progress_duration, left=start, 
                                  height=bar_height * 0.4,
                                  color='#4CAF50', alpha=0.8, zorder=3)
            
            # Critical path indicator
            if task['priority'] == 'critical':
                self.ax_gantt.barh(y_pos, duration * 0.02, left=start, 
                                  height=bar_height,
                                  color='#D32F2F', alpha=1.0, zorder=4)
            
            # Task label with duration
            text_x = start + timedelta(days=duration/2)
            label = f"{task['name']} ({duration}d)"
            
            # Truncate label if too long
            if len(label) > 30:
                label = f"{task['name'][:25]}... ({duration}d)"
            
            self.ax_gantt.text(text_x, y_pos, label,
                              ha='center', va='center', fontsize=8,
                              fontweight='bold', color='white', zorder=5)
    
    def _draw_metrics_panel(self, standards_data: Dict, tasks: List[Dict]):
        """Draw standards metrics panel on right side"""
        self.ax_metrics.axis('off')
        
        # Title
        y_pos = 0.98
        self.ax_metrics.text(0.5, y_pos, 'Standards Metrics',
                            ha='center', va='top', fontsize=14,
                            fontweight='bold', transform=self.ax_metrics.transAxes)
        
        y_pos -= 0.06
        
        # ACI 318-19 Section
        if 'aci_318' in standards_data:
            aci_318 = standards_data['aci_318']
            
            self.ax_metrics.text(0.05, y_pos, 'ACI 318-19 Design',
                                ha='left', va='top', fontsize=11,
                                fontweight='bold', color='#1976D2',
                                transform=self.ax_metrics.transAxes)
            y_pos -= 0.04
            
            # Concrete strength
            fc_psi = aci_318.get('fc_psi', aci_318.get('concrete_typ_fc_psi', 4000))
            text = f"f'c = {fc_psi} psi"
            self.ax_metrics.text(0.1, y_pos, text, ha='left', va='top',
                                fontsize=9, transform=self.ax_metrics.transAxes)
            y_pos -= 0.035
            
            # Modulus
            Ec_psi = aci_318.get('Ec_psi', aci_318.get('concrete_typ_Ec_psi', 3605000))
            text = f"Ec = {Ec_psi/1e6:.2f} x 10^6 psi"
            self.ax_metrics.text(0.1, y_pos, text, ha='left', va='top',
                                fontsize=9, transform=self.ax_metrics.transAxes)
            y_pos -= 0.035
            
            # Phi factors
            phi_shear = aci_318.get('phi_shear', 0.75)
            text = f"phi (shear) = {phi_shear}"
            self.ax_metrics.text(0.1, y_pos, text, ha='left', va='top',
                                fontsize=9, transform=self.ax_metrics.transAxes)
            y_pos -= 0.035
            
            # Min curing days
            min_curing = aci_318.get('min_curing_days', 7)
            text = f"Min curing = {min_curing} days [HIGH confidence]"
            self.ax_metrics.text(0.1, y_pos, text, ha='left', va='top',
                                fontsize=9, transform=self.ax_metrics.transAxes)
            y_pos -= 0.05
        
        # ACI 347-04 Section (CRITICAL for scheduling)
        if 'aci_347' in standards_data:
            aci_347 = standards_data['aci_347']
            
            self.ax_metrics.text(0.05, y_pos, 'ACI 347-04 Formwork',
                                ha='left', va='top', fontsize=11,
                                fontweight='bold', color='#F57C00',
                                transform=self.ax_metrics.transAxes)
            y_pos -= 0.04
            
            # Form removal times
            slab_removal = aci_347.get('slab_removal_days', 7)
            text = f"Slab form removal = {slab_removal} days [HIGH]"
            self.ax_metrics.text(0.1, y_pos, text, ha='left', va='top',
                                fontsize=9, transform=self.ax_metrics.transAxes)
            y_pos -= 0.035
            
            beam_removal = aci_347.get('beam_removal_days', 14)
            text = f"Beam form removal = {beam_removal} days [HIGH]"
            self.ax_metrics.text(0.1, y_pos, text, ha='left', va='top',
                                fontsize=9, transform=self.ax_metrics.transAxes)
            y_pos -= 0.035
            
            # Lateral pressure
            lat_pressure = aci_347.get('lateral_pressure_psf', 600)
            text = f"Lateral pressure = {lat_pressure} psf"
            self.ax_metrics.text(0.1, y_pos, text, ha='left', va='top',
                                fontsize=9, transform=self.ax_metrics.transAxes)
            y_pos -= 0.05
        
        # Productivity Section (with confidence warning)
        if 'productivity' in standards_data:
            prod = standards_data['productivity']
            
            self.ax_metrics.text(0.05, y_pos, 'Productivity Estimates',
                                ha='left', va='top', fontsize=11,
                                fontweight='bold', color='#388E3C',
                                transform=self.ax_metrics.transAxes)
            y_pos -= 0.04
            
            # Confidence warning
            self.ax_metrics.text(0.1, y_pos, '[LOW confidence - not intl std]',
                                ha='left', va='top', fontsize=8,
                                color='#FF5722', style='italic',
                                transform=self.ax_metrics.transAxes)
            y_pos -= 0.035
            
            crew_size = prod.get('crew_size', 15)
            text = f"Crew size = {crew_size}"
            self.ax_metrics.text(0.1, y_pos, text, ha='left', va='top',
                                fontsize=9, transform=self.ax_metrics.transAxes)
            y_pos -= 0.035
            
            if 'rebar_kg_per_day' in prod:
                text = f"Rebar = {prod['rebar_kg_per_day']:.0f} kg/day"
                self.ax_metrics.text(0.1, y_pos, text, ha='left', va='top',
                                    fontsize=9, transform=self.ax_metrics.transAxes)
                y_pos -= 0.035
            
            if 'concrete_m3_per_day' in prod:
                text = f"Concrete = {prod['concrete_m3_per_day']:.1f} m3/day"
                self.ax_metrics.text(0.1, y_pos, text, ha='left', va='top',
                                    fontsize=9, transform=self.ax_metrics.transAxes)
                y_pos -= 0.05
        
        # Schedule Summary
        self.ax_metrics.text(0.05, y_pos, 'Schedule Summary',
                            ha='left', va='top', fontsize=11,
                            fontweight='bold', color='#5E35B1',
                            transform=self.ax_metrics.transAxes)
        y_pos -= 0.04
        
        # Calculate summary stats
        total_duration = 0
        critical_tasks = 0
        avg_progress = 0
        floor_count = 0
        
        if tasks:
            start_dates = [t['start_date'] for t in tasks]
            end_dates = [t['end_date'] for t in tasks]
            total_duration = (max(end_dates) - min(start_dates)).days
            critical_tasks = sum(1 for t in tasks if t['priority'] == 'critical')
            avg_progress = sum(t['progress'] for t in tasks) / len(tasks)
            floor_count = len(set(t.get('floor_num') for t in tasks if t.get('floor_num')))
        
        text = f"Total duration: {total_duration} days"
        self.ax_metrics.text(0.1, y_pos, text, ha='left', va='top',
                            fontsize=9, transform=self.ax_metrics.transAxes)
        y_pos -= 0.035
        
        text = f"Floors: {floor_count}"
        self.ax_metrics.text(0.1, y_pos, text, ha='left', va='top',
                            fontsize=9, transform=self.ax_metrics.transAxes)
        y_pos -= 0.035
        
        text = f"Critical tasks: {critical_tasks}"
        self.ax_metrics.text(0.1, y_pos, text, ha='left', va='top',
                            fontsize=9, transform=self.ax_metrics.transAxes)
        y_pos -= 0.035
        
        text = f"Avg progress: {avg_progress:.0f}%"
        self.ax_metrics.text(0.1, y_pos, text, ha='left', va='top',
                            fontsize=9, transform=self.ax_metrics.transAxes)
        y_pos -= 0.05
        
        # Floor sequence note
        self.ax_metrics.text(0.05, y_pos, 'Floor Sequence:',
                            ha='left', va='top', fontsize=10,
                            fontweight='bold', color='#D32F2F',
                            transform=self.ax_metrics.transAxes)
        y_pos -= 0.035
        
        self.ax_metrics.text(0.1, y_pos, 'Strictly sequential per',
                            ha='left', va='top', fontsize=8,
                            transform=self.ax_metrics.transAxes)
        y_pos -= 0.03
        self.ax_metrics.text(0.1, y_pos, 'ACI 347-04 form removal',
                            ha='left', va='top', fontsize=8,
                            transform=self.ax_metrics.transAxes)
        
        # Add metrics panel background
        rect = mpatches.FancyBboxPatch((0.02, 0.05), 0.96, 0.92,
                                      boxstyle="round,pad=0.01",
                                      facecolor='#F5F5F5',
                                      edgecolor='#BDBDBD',
                                      linewidth=1,
                                      transform=self.ax_metrics.transAxes,
                                      zorder=0)
        self.ax_metrics.add_patch(rect)
    
    def _style_chart(self, tasks: List[Dict]):
        """Style the Gantt chart"""
        # Title
        self.ax_gantt.set_title(self.title, fontsize=16, fontweight='bold',
                               pad=20, color='#212121')
        
        # Y-axis - show task names in display order
        task_names = [t['name'] for t in reversed(tasks)]
        self.ax_gantt.set_yticks(range(len(tasks)))
        self.ax_gantt.set_yticklabels(task_names, fontsize=9)
        self.ax_gantt.set_ylim(-0.5, len(tasks) - 0.5)
        
        # X-axis
        self.ax_gantt.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
        self.ax_gantt.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
        plt.setp(self.ax_gantt.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Grid
        self.ax_gantt.grid(True, axis='x', alpha=0.2, linestyle='--', linewidth=0.5)
        self.ax_gantt.set_axisbelow(True)
        
        # Spines
        self.ax_gantt.spines['top'].set_visible(False)
        self.ax_gantt.spines['right'].set_visible(False)
        
        # Background
        self.ax_gantt.set_facecolor('#FAFAFA')
        
        # Labels
        self.ax_gantt.set_xlabel('Timeline', fontsize=12, fontweight='bold')
        self.ax_gantt.set_ylabel('Tasks (Sequential Floor Order)', fontsize=12, fontweight='bold')
        
        # Legend
        legend_elements = []
        used_categories = set(t['category'].lower() for t in tasks)
        for cat in ['foundation', 'formwork', 'rebar', 'concrete', 'curing', 'finishes']:
            if cat in used_categories or cat in ['formwork', 'rebar', 'concrete', 'curing']:
                color = self.COLORS.get(cat, self.COLORS['default'])
                legend_elements.append(
                    mpatches.Patch(color=color, label=cat.title(), alpha=0.85)
                )
        
        legend_elements.append(
            mpatches.Patch(edgecolor='red', facecolor='white', linewidth=2, 
                          label='Critical Path')
        )
        
        self.ax_gantt.legend(handles=legend_elements, loc='lower right', 
                            fontsize=8, ncol=2)
    
    def save(self, filename: str, dpi: int = 300):
        """Save chart"""
        if self.fig:
            self.fig.savefig(filename, dpi=dpi, bbox_inches='tight',
                           facecolor='white', edgecolor='none')
            plt.close(self.fig)


def create_gantt_with_standards(building_data: Dict, standards_mgr) -> plt.Figure:
    """
    Create Gantt chart with real standards data displayed
    Uses ACI 347-04 for proper floor sequencing
    
    Args:
        building_data: Building specifications
        standards_mgr: StandardsManager instance
    """
    # Get standards data
    fc_psi = building_data.get('fc_psi', 4000)
    fy_psi = building_data.get('fy_psi', 60000)
    crew_size = building_data.get('crew_size', 6)
    
    # Get ACI 318 data
    concrete_props = standards_mgr.get_concrete_properties(fc_psi)
    phi_shear = standards_mgr.get_phi_factor("shear")
    
    # Get ACI 347 data - CRITICAL for scheduling
    formwork_loads = standards_mgr.get_formwork_loads(use_motorized_carts=True)
    lateral_pressure = standards_mgr.get_lateral_pressure(
        placement_rate=2.5, temperature=70, concrete_height=10
    )
    
    # Get form removal times - CRITICAL for floor sequencing
    slab_removal = standards_mgr.get_formwork_removal_time(
        member_type="slab", span_ft=15.0, live_vs_dead="live_less_dead"
    )
    beam_removal = standards_mgr.get_formwork_removal_time(
        member_type="beam", span_ft=15.0, live_vs_dead="live_less_dead"
    )
    
    # Get productivity data (LOW confidence)
    rebar_prod = standards_mgr.get_productivity_rate("rebar", "fixing_slabs_footings")
    concrete_prod = standards_mgr.get_productivity_rate("concrete", "manual_laying")
    formwork_prod = standards_mgr.get_productivity_rate("concrete", "shuttering")
    
    # Compile standards data
    standards_data = {
        'aci_318': {
            'fc_psi': fc_psi,
            'Ec_psi': concrete_props.get('Ec_psi'),
            'phi_shear': phi_shear.get('value', 0.75),
            'min_curing_days': 7  # ACI 318-19 Table 26.1.3.5
        },
        'aci_347': {
            'lateral_pressure_psf': lateral_pressure.get('lateral_pressure_psf'),
            'vertical_load_psf': formwork_loads.get('value_psf'),
            'slab_removal_days': slab_removal.get('removal_time_days', 7),
            'beam_removal_days': beam_removal.get('removal_time_days', 14)
        },
        'productivity': {
            'crew_size': crew_size,
            'rebar_kg_per_day': (rebar_prod.get('productivity', {}).get('min', 0) + 
                                 rebar_prod.get('productivity', {}).get('max', 0)) / 2 * crew_size,
            'concrete_m3_per_day': (concrete_prod.get('productivity', {}).get('min', 0) + 
                                    concrete_prod.get('productivity', {}).get('max', 0)) / 2 * crew_size,
            'formwork_m2_per_day': (formwork_prod.get('productivity', {}).get('min', 0) + 
                                    formwork_prod.get('productivity', {}).get('max', 0)) / 2 * crew_size
        }
    }
    
    # Generate tasks with proper sequential floor scheduling
    tasks = _generate_tasks_sequential(building_data, standards_mgr)
    
    # Create chart
    gantt = ModernConstructionGantt(
        title=f"{building_data.get('floors', 10)}-Story Building Construction Schedule\n"
              f"(ACI 347-04 Sequential Floor Scheduling)"
    )
    
    return gantt.create_chart_with_metrics(tasks, standards_data)


def _generate_tasks_sequential(building_data: Dict, standards_mgr) -> List[Dict]:
    """
    Generate task list with STRICTLY SEQUENTIAL floor ordering
    Uses ACI 347-04 form removal times for proper floor cycle calculation
    
    CRITICAL: Floor N+1 CANNOT start until Floor N curing is complete
    """
    floors = building_data.get('floors', 10)
    floor_area = building_data.get('floor_area_m2', building_data.get('area', 200))
    slab_thickness = building_data.get('slab_thickness_mm', 150)
    crew_size = building_data.get('crew_size', 6)
    span_ft = building_data.get('span_ft', 15.0)
    
    # Get floor cycle time from standards manager
    floor_cycle = standards_mgr.get_floor_cycle_time(
        floor_area_m2=floor_area,
        slab_thickness_mm=slab_thickness,
        span_ft=span_ft,
        crew_size=crew_size,
        temperature_F=70.0
    )
    
    breakdown = floor_cycle.get('breakdown', {})
    formwork_days = breakdown.get('formwork_days', 5)
    rebar_days = breakdown.get('rebar_days', 4)
    concrete_days = breakdown.get('concrete_days', 2)
    curing_days = breakdown.get('wait_time_days', 7)  # ACI 347-04 form removal
    
    tasks = []
    current_day = 0
    
    # Foundation (before floors)
    tasks.append({
        'name': 'Foundation',
        'start': current_day,
        'duration': 14,
        'category': 'foundation',
        'priority': 'critical',
        'progress': 100,
        'floor': 0
    })
    current_day += 14
    
    # Generate floor tasks in STRICT SEQUENTIAL ORDER
    for floor_num in range(1, floors + 1):
        floor_start = current_day
        
        # Formwork
        tasks.append({
            'name': f'Floor {floor_num} Formwork',
            'start': floor_start,
            'duration': max(2, int(formwork_days)),
            'category': 'formwork',
            'priority': 'high' if floor_num <= 3 else 'medium',
            'progress': 100 if floor_num == 1 else 0,
            'floor': floor_num
        })
        formwork_end = floor_start + formwork_days
        
        # Rebar (after formwork)
        tasks.append({
            'name': f'Floor {floor_num} Rebar',
            'start': formwork_end,
            'duration': max(2, int(rebar_days)),
            'category': 'rebar',
            'priority': 'critical',
            'progress': 80 if floor_num == 1 else 0,
            'floor': floor_num
        })
        rebar_end = formwork_end + rebar_days
        
        # Concrete (after rebar)
        tasks.append({
            'name': f'Floor {floor_num} Concrete',
            'start': rebar_end,
            'duration': max(1, int(concrete_days)),
            'category': 'concrete',
            'priority': 'critical',
            'progress': 50 if floor_num == 1 else 0,
            'floor': floor_num
        })
        concrete_end = rebar_end + concrete_days
        
        # Curing (CRITICAL - from ACI 347-04)
        tasks.append({
            'name': f'Floor {floor_num} Curing',
            'start': concrete_end,
            'duration': int(curing_days),
            'category': 'curing',
            'priority': 'critical',
            'progress': 0,
            'floor': floor_num,
            'note': f'ACI 347-04: {curing_days} days min form removal'
        })
        curing_end = concrete_end + curing_days
        
        # Next floor starts AFTER this floor's curing is complete
        current_day = curing_end
    
    return tasks
