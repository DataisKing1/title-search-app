"""County-specific scraping adapters"""
from typing import Dict, Type, Optional, Any
from app.scraping.base_adapter import BaseCountyAdapter
import logging

logger = logging.getLogger(__name__)

# Registry of county adapters
_ADAPTER_REGISTRY: Dict[str, Type[BaseCountyAdapter]] = {}


def register_adapter(county_name: str):
    """Decorator to register a county adapter"""
    def decorator(cls: Type[BaseCountyAdapter]):
        _ADAPTER_REGISTRY[county_name.lower()] = cls
        logger.debug(f"Registered adapter for {county_name}: {cls.__name__}")
        return cls
    return decorator


def get_adapter_for_county(county_name: str, config: Dict[str, Any]) -> Optional[BaseCountyAdapter]:
    """
    Get the appropriate adapter for a county.

    Args:
        county_name: Name of the county
        config: County configuration dict

    Returns:
        Instantiated adapter or None if not found
    """
    from app.scraping.adapters.denver_adapter import DenverCountyAdapter
    from app.scraping.adapters.el_paso_adapter import ElPasoCountyAdapter
    from app.scraping.adapters.arapahoe_adapter import ArapahoeCountyAdapter
    from app.scraping.adapters.jefferson_adapter import JeffersonCountyAdapter
    from app.scraping.adapters.generic_adapter import GenericCountyAdapter

    county_lower = county_name.lower().strip()

    # Check registry first
    if county_lower in _ADAPTER_REGISTRY:
        adapter_cls = _ADAPTER_REGISTRY[county_lower]
        logger.info(f"Using registered adapter {adapter_cls.__name__} for {county_name}")
        return adapter_cls(config)

    # Check for specific adapters by name
    adapter_map = {
        "denver": DenverCountyAdapter,
        "el paso": ElPasoCountyAdapter,
        "el_paso": ElPasoCountyAdapter,
        "arapahoe": ArapahoeCountyAdapter,
        "jefferson": JeffersonCountyAdapter,
    }

    if county_lower in adapter_map:
        adapter_cls = adapter_map[county_lower]
        logger.info(f"Using {adapter_cls.__name__} for {county_name}")
        return adapter_cls(config)

    # Check if config specifies an adapter type
    adapter_type = config.get("scraping_adapter", "").lower() if config else ""
    if adapter_type:
        if adapter_type == "denver":
            logger.info(f"Using DenverCountyAdapter (from config) for {county_name}")
            return DenverCountyAdapter(config)
        elif adapter_type in ["el_paso", "el paso"]:
            logger.info(f"Using ElPasoCountyAdapter (from config) for {county_name}")
            return ElPasoCountyAdapter(config)
        elif adapter_type == "arapahoe":
            logger.info(f"Using ArapahoeCountyAdapter (from config) for {county_name}")
            return ArapahoeCountyAdapter(config)
        elif adapter_type == "jefferson":
            logger.info(f"Using JeffersonCountyAdapter (from config) for {county_name}")
            return JeffersonCountyAdapter(config)
        elif adapter_type == "generic":
            logger.info(f"Using GenericCountyAdapter (from config) for {county_name}")
            return GenericCountyAdapter(config)

    # Check if county has a recorder URL - if so, use generic adapter
    if config and config.get("recorder_url"):
        logger.info(f"No specific adapter for {county_name}, using GenericCountyAdapter")
        return GenericCountyAdapter(config)

    # No adapter available
    logger.warning(f"No adapter available for {county_name} (no recorder URL)")
    return None


def list_supported_counties() -> Dict[str, str]:
    """List all counties with specific adapters"""
    from app.scraping.adapters.denver_adapter import DenverCountyAdapter
    from app.scraping.adapters.el_paso_adapter import ElPasoCountyAdapter
    from app.scraping.adapters.arapahoe_adapter import ArapahoeCountyAdapter
    from app.scraping.adapters.jefferson_adapter import JeffersonCountyAdapter

    adapters = {
        "denver": DenverCountyAdapter.__name__,
        "el paso": ElPasoCountyAdapter.__name__,
        "arapahoe": ArapahoeCountyAdapter.__name__,
        "jefferson": JeffersonCountyAdapter.__name__,
    }

    # Add registered adapters
    for county, adapter_cls in _ADAPTER_REGISTRY.items():
        adapters[county] = adapter_cls.__name__

    return adapters


def get_adapter_class(adapter_name: str) -> Optional[Type[BaseCountyAdapter]]:
    """Get adapter class by name"""
    from app.scraping.adapters.denver_adapter import DenverCountyAdapter
    from app.scraping.adapters.el_paso_adapter import ElPasoCountyAdapter
    from app.scraping.adapters.arapahoe_adapter import ArapahoeCountyAdapter
    from app.scraping.adapters.jefferson_adapter import JeffersonCountyAdapter
    from app.scraping.adapters.generic_adapter import GenericCountyAdapter

    adapter_map = {
        "denver": DenverCountyAdapter,
        "el_paso": ElPasoCountyAdapter,
        "el paso": ElPasoCountyAdapter,
        "arapahoe": ArapahoeCountyAdapter,
        "jefferson": JeffersonCountyAdapter,
        "generic": GenericCountyAdapter,
    }

    return adapter_map.get(adapter_name.lower())


__all__ = [
    "register_adapter",
    "get_adapter_for_county",
    "get_adapter_class",
    "list_supported_counties",
]
