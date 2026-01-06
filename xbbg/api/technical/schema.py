"""Dynamic schema discovery for Bloomberg Technical Analysis (TASVC).

This module discovers available technical studies from the Bloomberg TASVC service
schema and caches them to JSON for offline use.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
from typing import Any

logger = logging.getLogger(__name__)

# Cache file location
CACHE_DIR = Path(__file__).parent / "cached"
CACHE_FILE = CACHE_DIR / "tasvc_studies.json"

# Default parameter values by type
DEFAULT_VALUES = {
    "Int32": 14,
    "Int64": 14,
    "Float32": 2.0,
    "Float64": 2.0,
    "String": "PX_LAST",
    "Bool": True,
}


def _parse_blpapi_type(type_name: str) -> type:
    """Convert BLPAPI type name to Python type."""
    type_map = {
        "Int32": int,
        "Int64": int,
        "Float32": float,
        "Float64": float,
        "String": str,
        "Bool": bool,
    }
    return type_map.get(type_name, str)


def _get_default_for_param(param_name: str, type_name: str) -> Any:
    """Get sensible default value for a parameter."""
    param_lower = param_name.lower()

    # Period-related defaults
    if "period" in param_lower:
        if "sig" in param_lower:
            return 9
        if "1" in param_name:
            return 12
        if "2" in param_name:
            return 26
        if "3" in param_name:
            return 28
        # Stochastic %K and %D periods (e.g., periodK, periodD, periodDS, periodDSS)
        if param_name in ("periodK",):
            return 14
        if param_name in ("periodD", "periodDS", "periodDSS"):
            return 3
        return 14

    # Band-related defaults
    if "band" in param_lower:
        return 2.0

    # Price source defaults
    if "pricesource" in param_lower:
        if "high" in param_lower:
            return "PX_HIGH"
        if "low" in param_lower:
            return "PX_LOW"
        if "open" in param_lower:
            return "PX_OPEN"
        if "volume" in param_lower:
            return "PX_VOLUME"
        return "PX_LAST"

    # MA type defaults
    if "matype" in param_lower or "type" in param_lower:
        return "SMA"

    # Factor defaults
    if "factor" in param_lower:
        if "start" in param_lower or "accel" in param_lower:
            return 0.02
        if "max" in param_lower:
            return 0.2
        return 1.0

    return DEFAULT_VALUES.get(type_name)


def _derive_study_name(attr_name: str) -> str:
    """Derive user-friendly study name from attribute name.

    Args:
        attr_name: e.g., 'smavgStudyAttributes'

    Returns:
        User-friendly name like 'SMA' or 'BOLLINGER'
    """
    # Remove 'StudyAttributes' suffix
    base = attr_name.replace("StudyAttributes", "")

    # Common abbreviation mappings derived from the base name
    # These are common technical analysis naming conventions
    abbreviations = {
        "smavg": "SMA",
        "emavg": "EMA",
        "wmavg": "WMA",
        "tmavg": "TMA",
        "vmavg": "VMA",
        "boll": "BOLLINGER",
        "tas": "STOCHASTICS",
        "cmci": "CCI",
        "wlpr": "WILLIAMSR",
        "kltn": "KELTNER",
        "goc": "ICHIMOKU",
        "ptps": "PSAR",
        "chko": "CHAIKIN",
        "al": "AROON",
    }

    return abbreviations.get(base.lower(), base.upper())


def _derive_description(output_field: str) -> str:
    """Derive human-readable description from output field name.

    Args:
        output_field: e.g., 'SMAVG', 'RSI', 'MACD'

    Returns:
        Human-readable description
    """
    # Common technical analysis term expansions
    expansions = {
        "SMAVG": "Simple Moving Average",
        "EMAVG": "Exponential Moving Average",
        "WMAVG": "Weighted Moving Average",
        "TMAVG": "Triangular Moving Average",
        "VMAVG": "Variable Moving Average",
        "RSI": "Relative Strength Index",
        "MACD": "Moving Average Convergence Divergence",
        "BOLL": "Bollinger Bands",
        "ATR": "Average True Range",
        "DMI": "Directional Movement Index",
        "TAS": "Stochastic Oscillator",
        "ROC": "Rate of Change",
        "MOMENTUM": "Momentum",
        "CMCI": "Commodity Channel Index",
        "WLPR": "Williams %R",
        "KLTN": "Keltner Channels",
        "GOC": "Ichimoku Cloud",
        "PTPS": "Parabolic SAR",
        "HURST": "Hurst Exponent",
        "MAE": "Moving Average Envelope",
        "CHKO": "Chaikin Oscillator",
        "MAO": "Moving Average Oscillator",
        "ADO": "Accumulation/Distribution",
        "AL": "Aroon Lines",
        "VAT": "Volume Average",
        "TVAT": "Time Volume at Price",
        "PIVOT": "Pivot Points",
        "FG": "Fibonacci Grid",
        "TE": "Trading Envelope",
        "ETD": "Ease of Movement",
        "PD": "Price Delta",
        "RV": "Relative Volatility",
        "IPMAVG": "Interperiod Moving Average",
        "OR": "Opening Range",
        "PCR": "Put-Call Ratio",
        "REX": "Rex Oscillator",
        "OBV": "On Balance Volume",
        "MFI": "Money Flow Index",
        "TRIX": "Triple Exponential Average",
        "ULTOSC": "Ultimate Oscillator",
        "MAXMIN": "Maximum/Minimum",
        "TRENDER": "Trender",
        "BS": "Black-Scholes",
    }

    if output_field in expansions:
        return expansions[output_field]

    # Fallback: split camelCase/acronyms into words
    words = re.sub(r"([A-Z])", r" \1", output_field).strip()
    return words.title() if words else output_field


def discover_studies_from_service() -> dict[str, dict[str, Any]]:
    """Discover available studies from the live TASVC service schema.

    Returns:
        Dictionary of study definitions keyed by display name.

    Raises:
        RuntimeError: If Bloomberg connection fails.
    """
    try:
        import blpapi  # noqa: F401
    except ImportError:
        raise RuntimeError("blpapi not installed") from None

    from xbbg.core.infra import conn

    # Connect and get service
    service = conn.bbg_service(service="//blp/tasvc")

    # Get the studyRequest operation
    operation = service.getOperation("studyRequest")
    request_def = operation.requestDefinition()

    studies = {}

    # Navigate: requestDefinition -> typeDefinition -> studyRequest element
    # -> StudyRequest type -> studyAttributes element -> StudyAttributes type
    req_type = request_def.typeDefinition()

    # Find studyRequest element first
    study_req_elem = None
    for i in range(req_type.numElementDefinitions()):
        elem = req_type.getElementDefinition(i)
        if str(elem.name()) == "studyRequest":
            study_req_elem = elem
            break

    # Try direct approach if studyRequest element not found (req_type might be StudyRequest type)
    study_req_type = req_type if study_req_elem is None else study_req_elem.typeDefinition()

    # Find studyAttributes in StudyRequest
    study_attrs_elem = None
    for i in range(study_req_type.numElementDefinitions()):
        elem = study_req_type.getElementDefinition(i)
        if str(elem.name()) == "studyAttributes":
            study_attrs_elem = elem
            break

    if study_attrs_elem is None:
        raise RuntimeError("Could not find studyAttributes in schema")

    # studyAttributes is a CHOICE type containing all study attribute types
    study_attrs_type = study_attrs_elem.typeDefinition()

    for j in range(study_attrs_type.numElementDefinitions()):
        study_def = study_attrs_type.getElementDefinition(j)
        attr_name = str(study_def.name())

        if attr_name.endswith("StudyAttributes"):
            # Derive names from the attribute
            display_name = _derive_study_name(attr_name)
            output_field = attr_name.replace("StudyAttributes", "").upper()

            # Get parameters from this study type
            params = {}
            study_type_def = study_def.typeDefinition()

            for k in range(study_type_def.numElementDefinitions()):
                param_def = study_type_def.getElementDefinition(k)
                param_name = str(param_def.name())
                param_type = str(param_def.typeDefinition().name())

                params[param_name] = {
                    "type": param_type,
                    "default": _get_default_for_param(param_name, param_type),
                    "description": param_name,
                }

            studies[display_name] = {
                "attribute": attr_name,
                "output": output_field,
                "description": _derive_description(output_field),
                "params": params,
            }

    return studies


def save_cache(studies: dict[str, dict[str, Any]]) -> None:
    """Save studies to cache file."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Convert type objects to strings for JSON serialization
    serializable = {}
    for name, info in studies.items():
        serializable[name] = {
            "attribute": info["attribute"],
            "output": info["output"],
            "description": info["description"],
            "params": {
                pname: {
                    "type": pinfo["type"] if isinstance(pinfo["type"], str) else pinfo["type"].__name__,
                    "default": pinfo["default"],
                    "description": pinfo["description"],
                }
                for pname, pinfo in info["params"].items()
            },
        }

    with open(CACHE_FILE, "w") as f:
        json.dump(serializable, f, indent=2)

    logger.info(f"Saved {len(studies)} studies to {CACHE_FILE}")


def load_cache() -> dict[str, dict[str, Any]] | None:
    """Load studies from cache file.

    Returns:
        Dictionary of study definitions, or None if cache doesn't exist.
    """
    if not CACHE_FILE.exists():
        return None

    with open(CACHE_FILE) as f:
        data = json.load(f)

    # Convert type strings back to type objects
    studies = {}
    for name, info in data.items():
        studies[name] = {
            "attribute": info["attribute"],
            "output": info["output"],
            "description": info["description"],
            "params": {
                pname: {
                    "type": _parse_blpapi_type(pinfo["type"]),
                    "default": pinfo["default"],
                    "description": pinfo["description"],
                }
                for pname, pinfo in info["params"].items()
            },
        }

    return studies


def get_studies(refresh: bool = False) -> dict[str, dict[str, Any]]:
    """Get available studies, using cache or discovering from service.

    Args:
        refresh: If True, force re-discovery from Bloomberg service.

    Returns:
        Dictionary of study definitions.
    """
    if not refresh:
        cached = load_cache()
        if cached is not None:
            return cached

    # Try to discover from live service
    try:
        studies = discover_studies_from_service()
        save_cache(studies)
        return studies
    except Exception as e:
        logger.warning(f"Could not discover studies from service: {e}")

        # Try to load from cache as fallback
        cached = load_cache()
        if cached is not None:
            logger.info("Using cached study definitions")
            return cached

        raise RuntimeError(
            "No cached studies available and cannot connect to Bloomberg. "
            "Connect to Bloomberg first to discover available studies."
        ) from None


def refresh_cache() -> dict[str, dict[str, Any]]:
    """Force refresh the study cache from Bloomberg service.

    Returns:
        Dictionary of newly discovered studies.
    """
    return get_studies(refresh=True)
