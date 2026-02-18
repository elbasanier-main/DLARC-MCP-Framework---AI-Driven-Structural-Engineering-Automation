try:
    from .visualization_report_module import ComprehensiveConstructionReportGenerator
except ImportError:
    pass
try:
    from .modern_gantt_with_metrics import ModernConstructionGantt
except ImportError:
    pass
