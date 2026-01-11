"""Court records scraping adapters"""
from typing import Dict, Type, Optional, Any
from app.scraping.court.base_court_adapter import BaseCourtAdapter, CourtSearchResult, CaseType, CaseStatus
import logging

logger = logging.getLogger(__name__)

# Registry of court adapters by state
_COURT_ADAPTER_REGISTRY: Dict[str, Type[BaseCourtAdapter]] = {}


def register_court_adapter(state: str):
    """Decorator to register a court adapter for a state"""
    def decorator(cls: Type[BaseCourtAdapter]):
        _COURT_ADAPTER_REGISTRY[state.upper()] = cls
        logger.debug(f"Registered court adapter for {state}: {cls.__name__}")
        return cls
    return decorator


def get_court_adapter(state: str, config: Dict[str, Any]) -> Optional[BaseCourtAdapter]:
    """
    Get the appropriate court adapter for a state.

    Args:
        state: State code (e.g., "CO")
        config: Configuration dict

    Returns:
        Instantiated adapter or None if not found
    """
    from app.scraping.court.colorado_courts import ColoradoCourtsAdapter

    state_upper = state.upper().strip()

    # Check registry first
    if state_upper in _COURT_ADAPTER_REGISTRY:
        adapter_cls = _COURT_ADAPTER_REGISTRY[state_upper]
        logger.info(f"Using registered court adapter {adapter_cls.__name__} for {state}")
        return adapter_cls(config)

    # Direct mapping for supported states
    state_adapters = {
        "CO": ColoradoCourtsAdapter,
        "COLORADO": ColoradoCourtsAdapter,
    }

    if state_upper in state_adapters:
        adapter_cls = state_adapters[state_upper]
        logger.info(f"Using {adapter_cls.__name__} for {state}")
        return adapter_cls(config)

    logger.warning(f"No court adapter available for state: {state}")
    return None


def list_supported_states() -> Dict[str, str]:
    """List all states with court adapters"""
    from app.scraping.court.colorado_courts import ColoradoCourtsAdapter

    adapters = {
        "CO": ColoradoCourtsAdapter.__name__,
    }

    # Add registered adapters
    for state, adapter_cls in _COURT_ADAPTER_REGISTRY.items():
        adapters[state] = adapter_cls.__name__

    return adapters


__all__ = [
    "BaseCourtAdapter",
    "CourtSearchResult",
    "CaseType",
    "CaseStatus",
    "register_court_adapter",
    "get_court_adapter",
    "list_supported_states",
]
