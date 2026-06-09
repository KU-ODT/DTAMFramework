"""
Initialization module for utils package
"""

__all__ = ['SafetyMetricsCalculator', 'SafetyMetrics', 'ThreadManager', 'ProcessingResult', 'ThreadState']


def __getattr__(name):
    """Lazy exports to avoid circular imports during detector initialization."""
    if name in {'SafetyMetricsCalculator', 'SafetyMetrics'}:
        from .safety_metrics import SafetyMetricsCalculator, SafetyMetrics
        return {
            'SafetyMetricsCalculator': SafetyMetricsCalculator,
            'SafetyMetrics': SafetyMetrics,
        }[name]
    if name in {'ThreadManager', 'ProcessingResult', 'ThreadState'}:
        from .thread_manager import ThreadManager, ProcessingResult, ThreadState
        return {
            'ThreadManager': ThreadManager,
            'ProcessingResult': ProcessingResult,
            'ThreadState': ThreadState,
        }[name]
    raise AttributeError(name)
