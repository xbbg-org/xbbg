"""Field type cache for intelligent Bloomberg field type resolution.

This module implements the four-tier type resolution hierarchy:
1. Manual overrides (field_types parameter)
2. Local Parquet cache (~/.xbbg/field_cache.parquet)
3. Runtime API query (//blp/apiflds)
4. Hardcoded defaults

Bloomberg field types (ftype) map to Arrow types as follows:
- Double, Float → Float64
- Int32, Int64, Integer → Int64
- String, Character → Utf8
- Date → Date32
- Time, Datetime → Timestamp
- Boolean → Boolean
- Bulk/Sequence → Utf8 (serialized)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# Default cache location
DEFAULT_CACHE_DIR = Path.home() / ".xbbg"
DEFAULT_CACHE_FILE = DEFAULT_CACHE_DIR / "field_cache.parquet"


@dataclass
class FieldInfo:
    """Metadata for a Bloomberg field."""

    field_id: str
    mnemonic: str
    ftype: str
    description: str | None = None
    category: str | None = None
    arrow_type: str | None = None
    cached_at: datetime | None = None


# Bloomberg ftype → Arrow type string mapping
# These strings match what we use in RequestParams.field_types
FTYPE_TO_ARROW: dict[str, str] = {
    # Numeric types
    "Double": "float64",
    "Float": "float64",
    "Real": "float64",
    "Price": "float64",
    "Int32": "int64",
    "Int64": "int64",
    "Integer": "int64",
    # String types
    "String": "string",
    "Character": "string",
    "Char": "string",
    # Date/time types
    "Date": "date32",
    "Time": "timestamp",
    "Datetime": "timestamp",
    "DateTime": "timestamp",
    # Boolean
    "Boolean": "bool",
    "Bool": "bool",
    # Bulk data (sequences) - serialize as string
    "Bulk": "string",
    "Sequence": "string",
    # Fallback
    "": "string",
}

# Hardcoded defaults for common fields (tier 4)
# These are used when API query fails or for offline usage
HARDCODED_FIELD_TYPES: dict[str, str] = {
    # Price fields
    "PX_LAST": "float64",
    "PX_OPEN": "float64",
    "PX_HIGH": "float64",
    "PX_LOW": "float64",
    "PX_CLOSE": "float64",
    "PX_BID": "float64",
    "PX_ASK": "float64",
    "PX_MID": "float64",
    "LAST_PRICE": "float64",
    "OPEN": "float64",
    "HIGH": "float64",
    "LOW": "float64",
    "CLOSE": "float64",
    # Volume fields
    "VOLUME": "int64",
    "PX_VOLUME": "int64",
    "VOLUME_AVG_30D": "float64",
    # Fundamental fields
    "CUR_MKT_CAP": "float64",
    "PE_RATIO": "float64",
    "PX_TO_BOOK_RATIO": "float64",
    "DIVIDEND_YIELD": "float64",
    "EPS_GROWTH": "float64",
    # String fields
    "NAME": "string",
    "SECURITY_NAME": "string",
    "LONG_COMP_NAME": "string",
    "TICKER": "string",
    "ID_ISIN": "string",
    "ID_CUSIP": "string",
    "ID_SEDOL1": "string",
    "CRNCY": "string",
    "COUNTRY": "string",
    "GICS_SECTOR_NAME": "string",
    "GICS_INDUSTRY_NAME": "string",
    # Date fields
    "ANNOUNCE_DT": "date32",
    "DVD_EX_DT": "date32",
    "DVD_RECORD_DT": "date32",
    "LAST_UPDATE_DT": "date32",
    # Boolean fields
    "IS_INDEX_MEMBER": "bool",
}


class FieldTypeCache:
    """Cache for Bloomberg field type information.

    Provides intelligent type resolution using a four-tier hierarchy:
    1. Manual overrides passed directly to functions
    2. Local Parquet cache for frequently used fields
    3. Runtime API queries to //blp/apiflds
    4. Hardcoded defaults for common fields

    Example:
        >>> cache = FieldTypeCache()
        >>> types = cache.resolve_types(["PX_LAST", "NAME", "VOLUME"])
        {'PX_LAST': 'float64', 'NAME': 'string', 'VOLUME': 'int64'}

        >>> # Pre-cache fields for offline use
        >>> await cache.cache_field_types(["PX_LAST", "PX_OPEN", "PX_HIGH"])
    """

    def __init__(self, cache_path: Path | str | None = None):
        """Initialize the field type cache.

        Args:
            cache_path: Path to cache file. Defaults to ~/.xbbg/field_cache.parquet
        """
        self._cache_path = Path(cache_path) if cache_path else DEFAULT_CACHE_FILE
        self._memory_cache: dict[str, FieldInfo] = {}
        self._cache_loaded = False

    @property
    def cache_path(self) -> Path:
        """Path to the cache file."""
        return self._cache_path

    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_cache(self) -> None:
        """Load cache from Parquet file into memory."""
        if self._cache_loaded:
            return

        if not self._cache_path.exists():
            self._cache_loaded = True
            return

        try:
            import pyarrow.parquet as pq

            table = pq.read_table(self._cache_path)
            df = table.to_pydict()

            for i in range(len(df.get("mnemonic", []))):
                mnemonic = df["mnemonic"][i]
                if mnemonic:
                    self._memory_cache[mnemonic] = FieldInfo(
                        field_id=df.get("field_id", [""])[i] or "",
                        mnemonic=mnemonic,
                        ftype=df.get("ftype", [""])[i] or "",
                        description=df.get("description", [None])[i],
                        category=df.get("category", [None])[i],
                        arrow_type=df.get("arrow_type", [None])[i],
                        cached_at=df.get("cached_at", [None])[i],
                    )

            logger.debug("Loaded %d fields from cache", len(self._memory_cache))
        except Exception as e:
            logger.warning("Failed to load field cache: %s", e)

        self._cache_loaded = True

    def _save_cache(self) -> None:
        """Save memory cache to Parquet file."""
        if not self._memory_cache:
            return

        try:
            import pyarrow as pa
            import pyarrow.parquet as pq

            self._ensure_cache_dir()

            # Build arrays from cache
            field_ids = []
            mnemonics = []
            ftypes = []
            descriptions = []
            categories = []
            arrow_types = []
            cached_ats = []

            for info in self._memory_cache.values():
                field_ids.append(info.field_id)
                mnemonics.append(info.mnemonic)
                ftypes.append(info.ftype)
                descriptions.append(info.description)
                categories.append(info.category)
                arrow_types.append(info.arrow_type)
                cached_ats.append(info.cached_at)

            table = pa.table(
                {
                    "field_id": field_ids,
                    "mnemonic": mnemonics,
                    "ftype": ftypes,
                    "description": descriptions,
                    "category": categories,
                    "arrow_type": arrow_types,
                    "cached_at": cached_ats,
                }
            )

            pq.write_table(table, self._cache_path)
            logger.debug("Saved %d fields to cache", len(self._memory_cache))
        except Exception as e:
            logger.warning("Failed to save field cache: %s", e)

    def _ftype_to_arrow(self, ftype: str) -> str:
        """Convert Bloomberg ftype to Arrow type string."""
        return FTYPE_TO_ARROW.get(ftype, "string")

    def resolve_types(
        self,
        fields: Sequence[str],
        overrides: dict[str, str] | None = None,
        use_cache: bool = True,
        use_hardcoded: bool = True,
    ) -> dict[str, str]:
        """Resolve Arrow types for a list of fields.

        Uses the four-tier resolution hierarchy:
        1. Manual overrides (if provided)
        2. Local cache (if use_cache=True and field is cached)
        3. Hardcoded defaults (if use_hardcoded=True)
        4. Default to "string"

        Note: This method does NOT query //blp/apiflds. Use cache_field_types()
        to populate the cache first, or call aresolve_types() for async resolution.

        Args:
            fields: List of field mnemonics to resolve
            overrides: Manual type overrides (highest priority)
            use_cache: Whether to check local cache
            use_hardcoded: Whether to use hardcoded defaults

        Returns:
            Dict mapping field names to Arrow type strings
        """
        result: dict[str, str] = {}
        overrides = overrides or {}

        self._load_cache()

        for field in fields:
            # Tier 1: Manual overrides
            if field in overrides:
                result[field] = overrides[field]
                continue

            # Tier 2: Local cache
            if use_cache and field in self._memory_cache:
                info = self._memory_cache[field]
                if info.arrow_type:
                    result[field] = info.arrow_type
                    continue
                if info.ftype:
                    result[field] = self._ftype_to_arrow(info.ftype)
                    continue

            # Tier 3: Hardcoded defaults
            if use_hardcoded and field in HARDCODED_FIELD_TYPES:
                result[field] = HARDCODED_FIELD_TYPES[field]
                continue

            # Tier 4: Default to string
            result[field] = "string"

        return result

    async def aresolve_types(
        self,
        fields: Sequence[str],
        overrides: dict[str, str] | None = None,
        query_api: bool = True,
    ) -> dict[str, str]:
        """Async resolve Arrow types, querying //blp/apiflds for cache misses.

        Uses the full four-tier resolution hierarchy:
        1. Manual overrides (if provided)
        2. Local cache
        3. Runtime API query (if query_api=True)
        4. Hardcoded defaults

        Args:
            fields: List of field mnemonics to resolve
            overrides: Manual type overrides (highest priority)
            query_api: Whether to query //blp/apiflds for cache misses

        Returns:
            Dict mapping field names to Arrow type strings
        """
        result: dict[str, str] = {}
        overrides = overrides or {}
        missing_fields: list[str] = []

        self._load_cache()

        for field in fields:
            # Tier 1: Manual overrides
            if field in overrides:
                result[field] = overrides[field]
                continue

            # Tier 2: Local cache
            if field in self._memory_cache:
                info = self._memory_cache[field]
                if info.arrow_type:
                    result[field] = info.arrow_type
                    continue
                if info.ftype:
                    result[field] = self._ftype_to_arrow(info.ftype)
                    continue

            # Tier 3: Need to query API
            missing_fields.append(field)

        # Query API for missing fields
        if query_api and missing_fields:
            try:
                await self.cache_field_types(missing_fields)

                # Retry resolution for missing fields
                for field in missing_fields:
                    if field in self._memory_cache:
                        info = self._memory_cache[field]
                        if info.arrow_type:
                            result[field] = info.arrow_type
                        elif info.ftype:
                            result[field] = self._ftype_to_arrow(info.ftype)
                        else:
                            result[field] = HARDCODED_FIELD_TYPES.get(field, "string")
                    else:
                        result[field] = HARDCODED_FIELD_TYPES.get(field, "string")
            except Exception as e:
                logger.warning("Failed to query field types: %s", e)
                # Fall back to hardcoded/defaults
                for field in missing_fields:
                    result[field] = HARDCODED_FIELD_TYPES.get(field, "string")
        else:
            # Use hardcoded/defaults for missing fields
            for field in missing_fields:
                result[field] = HARDCODED_FIELD_TYPES.get(field, "string")

        return result

    async def cache_field_types(self, fields: Sequence[str]) -> None:
        """Query //blp/apiflds and cache the results.

        Args:
            fields: List of field mnemonics to cache
        """
        from xbbg import arequest
        from xbbg.services import Operation, Service

        # Query field info
        result = await arequest(
            service=Service.APIFLDS,
            operation=Operation.FIELD_INFO,
            fields=list(fields),
        )

        # Convert to dict for easier access
        data = result.to_pydict() if hasattr(result, "to_pydict") else {}

        now = datetime.now()

        # Update memory cache
        mnemonics = data.get("mnemonic", [])
        for i, mnemonic in enumerate(mnemonics):
            if mnemonic:
                ftype = data.get("ftype", [""])[i] or ""
                self._memory_cache[mnemonic] = FieldInfo(
                    field_id=data.get("field_id", [""])[i] or "",
                    mnemonic=mnemonic,
                    ftype=ftype,
                    description=data.get("description", [None])[i],
                    category=data.get("category", [None])[i],
                    arrow_type=self._ftype_to_arrow(ftype),
                    cached_at=now,
                )

        # Save to disk
        self._save_cache()

    async def get_field_info(self, fields: Sequence[str]) -> list[FieldInfo]:
        """Get detailed field information.

        Args:
            fields: List of field mnemonics

        Returns:
            List of FieldInfo objects
        """
        self._load_cache()

        # Find missing fields
        missing = [f for f in fields if f not in self._memory_cache]
        if missing:
            await self.cache_field_types(missing)

        return [self._memory_cache.get(f, FieldInfo(field_id="", mnemonic=f, ftype="")) for f in fields]

    def clear_cache(self) -> None:
        """Clear both memory and disk cache."""
        self._memory_cache.clear()
        self._cache_loaded = False

        if self._cache_path.exists():
            try:
                self._cache_path.unlink()
                logger.debug("Deleted cache file: %s", self._cache_path)
            except Exception as e:
                logger.warning("Failed to delete cache file: %s", e)


# Module-level singleton
_default_cache: FieldTypeCache | None = None


def get_field_cache() -> FieldTypeCache:
    """Get the default field type cache singleton."""
    global _default_cache
    if _default_cache is None:
        _default_cache = FieldTypeCache()
    return _default_cache


# Convenience functions using the default cache


def resolve_field_types(
    fields: Sequence[str],
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Resolve Arrow types for fields using local cache and hardcoded defaults.

    For async resolution with API queries, use aresolve_field_types().

    Args:
        fields: List of field mnemonics
        overrides: Manual type overrides

    Returns:
        Dict mapping field names to Arrow type strings
    """
    return get_field_cache().resolve_types(fields, overrides)


async def aresolve_field_types(
    fields: Sequence[str],
    overrides: dict[str, str] | None = None,
    query_api: bool = True,
) -> dict[str, str]:
    """Async resolve Arrow types, querying //blp/apiflds for cache misses.

    Args:
        fields: List of field mnemonics
        overrides: Manual type overrides
        query_api: Whether to query API for cache misses

    Returns:
        Dict mapping field names to Arrow type strings
    """
    return await get_field_cache().aresolve_types(fields, overrides, query_api)


async def cache_field_types(fields: Sequence[str]) -> None:
    """Pre-cache field types from //blp/apiflds.

    Args:
        fields: List of field mnemonics to cache
    """
    await get_field_cache().cache_field_types(fields)


async def get_field_info(fields: Sequence[str]) -> list[FieldInfo]:
    """Get detailed field information from cache or API.

    Args:
        fields: List of field mnemonics

    Returns:
        List of FieldInfo objects
    """
    return await get_field_cache().get_field_info(fields)


def clear_field_cache() -> None:
    """Clear the field type cache."""
    get_field_cache().clear_cache()
