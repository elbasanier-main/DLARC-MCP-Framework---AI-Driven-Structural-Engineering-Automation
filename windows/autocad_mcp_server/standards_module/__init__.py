from .standards_manager import StandardsManager

_instance = None

def get_standards_manager():
    global _instance
    if _instance is None:
        _instance = StandardsManager()
    return _instance
