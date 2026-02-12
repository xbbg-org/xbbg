"""Bloomberg lookup and utility functions.

Provides functions for field information, field search, security lookup, and portfolio queries.
"""

from __future__ import annotations

from collections.abc import Iterator
import logging
from typing import Any

import narwhals as nw
import pyarrow as pa

from xbbg.backend import Backend, Format
from xbbg.core.infra import conn as conn_module
from xbbg.core.infra.blpapi_wrapper import blpapi
from xbbg.core.utils import utils
from xbbg.io.convert import _convert_backend
from xbbg.options import get_backend

logger = logging.getLogger(__name__)

__all__ = [
    "bfld",
    "abfld",
    "fieldInfo",
    "afieldInfo",
    "fieldSearch",
    "afieldSearch",
    "blkp",
    "ablkp",
    "lookupSecurity",
    "alookupSecurity",
    "bport",
    "getPortfolio",
    "getBlpapiVersion",
]


def _process_field_info_msg(msg: Any, **kwargs) -> Iterator[dict[str, Any]]:
    field_data = msg.getElement(blpapi.Name("fieldData"))
    for i in range(field_data.numValues()):
        field_elem = field_data.getValueAsElement(i)
        if field_elem.hasElement(blpapi.Name("fieldError")):
            error_msg = field_elem.getElement(blpapi.Name("fieldError")).getElementAsString(blpapi.Name("message"))
            raise ValueError(f"Bad field: {error_msg}")
        field_id = field_elem.getElementAsString(blpapi.Name("id"))
        field_info_elem = field_elem.getElement(blpapi.Name("fieldInfo"))
        yield {
            "id": field_id,
            "mnemonic": field_info_elem.getElementAsString(blpapi.Name("mnemonic")),
            "datatype": field_info_elem.getElementAsString(blpapi.Name("datatype")),
            "ftype": field_info_elem.getElementAsString(blpapi.Name("ftype")),
        }


def _process_field_search_msg(msg: Any, **kwargs) -> Iterator[dict[str, Any]]:
    field_data = msg.getElement(blpapi.Name("fieldData"))
    for i in range(field_data.numValues()):
        field_elem = field_data.getValueAsElement(i)
        field_id = field_elem.getElementAsString(blpapi.Name("id"))
        if field_elem.hasElement(blpapi.Name("fieldInfo")):
            field_info = field_elem.getElement(blpapi.Name("fieldInfo"))
            yield {
                "id": field_id,
                "mnemonic": field_info.getElementAsString(blpapi.Name("mnemonic")),
                "description": field_info.getElementAsString(blpapi.Name("description")),
            }
        else:
            field_error = field_elem.getElement(blpapi.Name("fieldError"))
            error_msg = field_error.getElementAsString(blpapi.Name("message"))
            raise ValueError(f"Field error for {field_id}: {error_msg}")


def _process_lookup_msg(msg: Any, **kwargs) -> Iterator[dict[str, Any]]:
    verbose = kwargs.get("verbose", False)
    if msg.hasElement(blpapi.Name("responseError")):
        error_msg = msg.getElement(blpapi.Name("responseError"))
        logger.error("REQUEST FAILED: %s", error_msg)
        return

    response = msg.asElement()
    if str(response.name()) != "InstrumentListResponse":
        raise ValueError("Not a valid InstrumentListResponse")

    response_results = response.getElement(blpapi.Name("results"))
    if verbose:
        logger.debug("Response contains %d items", response_results.numValues())

    for i in range(response_results.numValues()):
        item = response_results.getValueAsElement(i)
        security = item.getElementAsString(blpapi.Name("security"))
        description = item.getElementAsString(blpapi.Name("description"))
        if verbose:
            logger.debug("%s\t\t%s", security, description)
        yield {
            "security": security,
            "description": description,
        }


async def afieldInfo(
    fields: str | list[str],
    *,
    backend: Backend | None = None,
    **kwargs,
) -> Any:
    """Get metadata about Bloomberg fields.

    Retrieves field information including ID, mnemonic, data type, and field type
    for the specified Bloomberg fields.

    Args:
        fields: Single field or list of fields to query.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        **kwargs: Infrastructure options (e.g., port, server).

    Returns:
        DataFrame: Field information with columns: id, mnemonic, datatype, ftype.

    Examples:
        >>> from xbbg import blp
        >>> # Get info for single field
        >>> info = blp.fieldInfo("PX_LAST")  # doctest: +SKIP
        >>> # Get info for multiple fields
        >>> info = blp.fieldInfo(["PX_LAST", "VOLUME"])  # doctest: +SKIP
    """
    field_list = utils.normalize_flds(fields)
    service_name = "//blp/apiflds"
    await conn_module._session_manager.aget_session(**kwargs)
    field_info_service = await conn_module._session_manager.aget_service(service_name, **kwargs)

    results = []
    for field in field_list:
        request = field_info_service.createRequest("FieldInfoRequest")
        request.append(blpapi.Name("id"), field)
        request.set(blpapi.Name("returnFieldDocumentation"), False)

        field_results = await conn_module.arequest(
            request,
            _process_field_info_msg,
            service=service_name,
            **kwargs,
        )
        if len(field_results) > 1:
            raise ValueError(f"getFieldType: too many fields returned for {field}")
        results.extend(field_results)

    # Convert to requested backend
    actual_backend = backend if backend is not None else get_backend()
    arrow_table = pa.Table.from_pylist(results)
    return _convert_backend(nw.from_native(arrow_table), actual_backend)


def fieldInfo(
    fields: str | list[str],
    *,
    backend: Backend | None = None,
    **kwargs,
) -> Any:
    """Get metadata about Bloomberg fields.

    Retrieves field information including ID, mnemonic, data type, and field type
    for the specified Bloomberg fields.

    Args:
        fields: Single field or list of fields to query.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        **kwargs: Infrastructure options (e.g., port, server).

    Returns:
        DataFrame: Field information with columns: id, mnemonic, datatype, ftype.

    Examples:
        >>> from xbbg import blp
        >>> # Get info for single field
        >>> info = blp.fieldInfo("PX_LAST")  # doctest: +SKIP
        >>> # Get info for multiple fields
        >>> info = blp.fieldInfo(["PX_LAST", "VOLUME"])  # doctest: +SKIP
    """
    return conn_module._run_sync(afieldInfo(fields, backend=backend, **kwargs))


async def afieldSearch(
    searchterm: str,
    *,
    backend: Backend | None = None,
    **kwargs,
) -> Any:
    """Search for Bloomberg fields by name or description.

    Searches for Bloomberg fields matching the given search term. Useful for
    discovering fields when you know what you want but not the exact field name.

    Args:
        searchterm: Search term to match against field names/descriptions.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        **kwargs: Infrastructure options (e.g., port, server).

    Returns:
        DataFrame: Matching fields with columns: id, mnemonic, description.

    Examples:
        >>> from xbbg import blp
        >>> # Search for VWAP-related fields
        >>> results = blp.fieldSearch("vwap")  # doctest: +SKIP
        >>> # Search for volume fields
        >>> results = blp.fieldSearch("volume")  # doctest: +SKIP
    """
    service_name = "//blp/apiflds"
    await conn_module._session_manager.aget_session(**kwargs)
    field_info_service = await conn_module._session_manager.aget_service(service_name, **kwargs)

    # Create FieldSearchRequest
    request = field_info_service.createRequest("FieldSearchRequest")
    request.set(blpapi.Name("searchSpec"), searchterm)
    request.set(blpapi.Name("returnFieldDocumentation"), False)

    results = await conn_module.arequest(
        request,
        _process_field_search_msg,
        service=service_name,
        **kwargs,
    )

    # Convert to requested backend
    actual_backend = backend if backend is not None else get_backend()
    arrow_table = pa.Table.from_pylist(results)
    return _convert_backend(nw.from_native(arrow_table), actual_backend)


def fieldSearch(
    searchterm: str,
    *,
    backend: Backend | None = None,
    **kwargs,
) -> Any:
    """Search for Bloomberg fields by name or description.

    Searches for Bloomberg fields matching the given search term. Useful for
    discovering fields when you know what you want but not the exact field name.

    Args:
        searchterm: Search term to match against field names/descriptions.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        **kwargs: Infrastructure options (e.g., port, server).

    Returns:
        DataFrame: Matching fields with columns: id, mnemonic, description.

    Examples:
        >>> from xbbg import blp
        >>> # Search for VWAP-related fields
        >>> results = blp.fieldSearch("vwap")  # doctest: +SKIP
        >>> # Search for volume fields
        >>> results = blp.fieldSearch("volume")  # doctest: +SKIP
    """
    return conn_module._run_sync(afieldSearch(searchterm, backend=backend, **kwargs))


async def alookupSecurity(
    query: str,
    yellowkey: str = "none",
    language: str = "none",
    max_results: int = 20,
    verbose: bool = False,
    *,
    backend: Backend | None = None,
    **kwargs,
) -> Any:
    """Look up securities/tickers by company name.

    Searches for securities matching the given query string. Useful for finding
    tickers when you only know the company name.

    Args:
        query: Company name or search term (e.g., "IBM", "Apple").
        yellowkey: Asset class filter. One of: none, cmdt, eqty, muni, prfd,
            clnt, mmkt, govt, corp, indx, curr, mtge. Defaults to 'none'.
        language: Language override. One of: none, english, kanji, french,
            german, spanish, portuguese, italian, chinese_trad, korean,
            chinese_simp, russian. Defaults to 'none'.
        max_results: Maximum number of results to return (capped at 1000 by API).
            Defaults to 20.
        verbose: Whether to print verbose output. Defaults to False.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        **kwargs: Infrastructure options (e.g., port, server).

    Returns:
        DataFrame: Matching securities with columns: security, description.

    Examples:
        >>> from xbbg import blp
        >>> # Search for IBM
        >>> results = blp.lookupSecurity("IBM")  # doctest: +SKIP
        >>> # Search with asset class filter
        >>> results = blp.lookupSecurity("IBM", yellowkey="eqty")  # doctest: +SKIP
        >>> # Increase max results
        >>> results = blp.lookupSecurity("Apple", max_results=100)  # doctest: +SKIP
    """
    service_name = "//blp/instruments"
    await conn_module._session_manager.aget_session(**kwargs)
    instruments_service = await conn_module._session_manager.aget_service(service_name, **kwargs)

    # Map yellowkey to Bloomberg format
    yellowkey_map = {
        "none": "YK_FILTER_NONE",
        "cmdt": "YK_FILTER_CMDT",
        "eqty": "YK_FILTER_EQTY",
        "muni": "YK_FILTER_MUNI",
        "prfd": "YK_FILTER_PRFD",
        "clnt": "YK_FILTER_CLNT",
        "mmkt": "YK_FILTER_MMKT",
        "govt": "YK_FILTER_GOVT",
        "corp": "YK_FILTER_CORP",
        "indx": "YK_FILTER_INDX",
        "curr": "YK_FILTER_CURR",
        "mtge": "YK_FILTER_MTGE",
    }
    yellowkey_filter = yellowkey_map.get(yellowkey.lower(), "YK_FILTER_NONE")

    # Map language to Bloomberg format
    language_map = {
        "none": "LANG_OVERRIDE_NONE",
        "english": "LANG_OVERRIDE_ENGLISH",
        "kanji": "LANG_OVERRIDE_KANJI",
        "french": "LANG_OVERRIDE_FRENCH",
        "german": "LANG_OVERRIDE_GERMAN",
        "spanish": "LANG_OVERRIDE_SPANISH",
        "portuguese": "LANG_OVERRIDE_PORTUGUESE",
        "italian": "LANG_OVERRIDE_ITALIAN",
        "chinese_trad": "LANG_OVERRIDE_CHINESE_TRAD",
        "korean": "LANG_OVERRIDE_KOREAN",
        "chinese_simp": "LANG_OVERRIDE_CHINESE_SIMP",
        "russian": "LANG_OVERRIDE_RUSSIAN",
    }
    language_override = language_map.get(language.lower(), "LANG_OVERRIDE_NONE")

    if max_results > 1000:
        logger.warning("max_results may be limited to 1000 by the Bloomberg API")

    # Create instrumentListRequest
    request = instruments_service.createRequest("instrumentListRequest")
    request.set(blpapi.Name("query"), query)
    request.set(blpapi.Name("yellowKeyFilter"), yellowkey_filter)
    request.set(blpapi.Name("languageOverride"), language_override)
    request.set(blpapi.Name("maxResults"), max_results)

    if verbose:
        logger.info("Sending lookup request: %s", request)

    results = await conn_module.arequest(
        request,
        _process_lookup_msg,
        service=service_name,
        verbose=verbose,
        **kwargs,
    )

    # Convert to requested backend
    actual_backend = backend if backend is not None else get_backend()
    arrow_table = pa.Table.from_pylist(results)
    return _convert_backend(nw.from_native(arrow_table), actual_backend)


def lookupSecurity(
    query: str,
    yellowkey: str = "none",
    language: str = "none",
    max_results: int = 20,
    verbose: bool = False,
    *,
    backend: Backend | None = None,
    **kwargs,
) -> Any:
    """Look up securities/tickers by company name.

    Searches for securities matching the given query string. Useful for finding
    tickers when you only know the company name.

    Args:
        query: Company name or search term (e.g., "IBM", "Apple").
        yellowkey: Asset class filter. One of: none, cmdt, eqty, muni, prfd,
            clnt, mmkt, govt, corp, indx, curr, mtge. Defaults to 'none'.
        language: Language override. One of: none, english, kanji, french,
            german, spanish, portuguese, italian, chinese_trad, korean,
            chinese_simp, russian. Defaults to 'none'.
        max_results: Maximum number of results to return (capped at 1000 by API).
            Defaults to 20.
        verbose: Whether to print verbose output. Defaults to False.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        **kwargs: Infrastructure options (e.g., port, server).

    Returns:
        DataFrame: Matching securities with columns: security, description.

    Examples:
        >>> from xbbg import blp
        >>> # Search for IBM
        >>> results = blp.lookupSecurity("IBM")  # doctest: +SKIP
        >>> # Search with asset class filter
        >>> results = blp.lookupSecurity("IBM", yellowkey="eqty")  # doctest: +SKIP
        >>> # Increase max results
        >>> results = blp.lookupSecurity("Apple", max_results=100)  # doctest: +SKIP
    """
    return conn_module._run_sync(
        alookupSecurity(
            query,
            yellowkey=yellowkey,
            language=language,
            max_results=max_results,
            verbose=verbose,
            backend=backend,
            **kwargs,
        )
    )


def getPortfolio(
    security: str,
    field: str,
    options: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
    verbose: bool = False,
    *,
    backend: Backend | None = None,
    format: Format | None = None,
    **kwargs,
) -> Any:
    """Get portfolio data for a security.

    This is a convenience wrapper around `bds()` that uses PortfolioDataRequest
    instead of ReferenceDataRequest. It's equivalent to calling
    `bds(security, field, use_port=True, ...)`.

    Args:
        security: Single security symbol in Bloomberg notation.
        field: Single Bloomberg query field.
        options: Optional named dictionary with option values.
        overrides: Optional named dictionary with override values.
        verbose: Whether to print verbose output. Defaults to False.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        format: Output format (e.g., Format.WIDE, Format.LONG). Defaults to global setting.
        **kwargs: Additional infrastructure options.

    Returns:
        DataFrame: Portfolio data.

    Examples:
        >>> from xbbg import blp
        >>> # Get portfolio data
        >>> portfolio = blp.getPortfolio("PORTFOLIO_NAME", "PORTFOLIO_MWEIGHT")  # doctest: +SKIP
    """
    from xbbg.api.reference.reference import bds

    # Merge options and overrides into kwargs
    all_kwargs = {**kwargs}
    if options:
        all_kwargs.update(options)
    if overrides:
        all_kwargs.update(overrides)

    return bds(security, field, use_port=True, verbose=verbose, backend=backend, format=format, **all_kwargs)


def bfld(
    fields: str | list[str] | None = None,
    *,
    search_spec: str | None = None,
    backend: Backend | None = None,
    **kwargs,
) -> Any:
    """Get field metadata or search for fields.

    This is the v1.0 unified field function that combines fieldInfo and fieldSearch.

    Args:
        fields: Single field or list of fields to get metadata for.
            Mutually exclusive with search_spec.
        search_spec: Search term to find fields by name/description.
            Mutually exclusive with fields.
        backend: Output backend (e.g., Backend.PANDAS, Backend.POLARS). Defaults to global setting.
        **kwargs: Infrastructure options (e.g., port, server).

    Returns:
        DataFrame: Field information or search results.

    Raises:
        ValueError: If neither fields nor search_spec is provided, or both are provided.

    Examples:
        >>> from xbbg import blp
        >>> # Get info for specific fields
        >>> info = blp.bfld(fields=["PX_LAST", "VOLUME"])  # doctest: +SKIP
        >>> # Search for fields by keyword
        >>> results = blp.bfld(search_spec="vwap")  # doctest: +SKIP
    """
    if fields is not None and search_spec is not None:
        raise ValueError("Cannot specify both 'fields' and 'search_spec'. Use one or the other.")
    if fields is None and search_spec is None:
        raise ValueError("Must specify either 'fields' or 'search_spec'.")

    if search_spec is not None:
        return fieldSearch(search_spec, backend=backend, **kwargs)
    # fields is guaranteed non-None here due to check above
    assert fields is not None
    return fieldInfo(fields, backend=backend, **kwargs)


async def abfld(
    fields: str | list[str] | None = None,
    *,
    search_spec: str | None = None,
    backend: Backend | None = None,
    **kwargs,
) -> Any:
    """Async version of bfld()."""
    if fields is not None and search_spec is not None:
        raise ValueError("Cannot specify both 'fields' and 'search_spec'. Use one or the other.")
    if fields is None and search_spec is None:
        raise ValueError("Must specify either 'fields' or 'search_spec'.")

    if search_spec is not None:
        return await afieldSearch(search_spec, backend=backend, **kwargs)
    assert fields is not None
    return await afieldInfo(fields, backend=backend, **kwargs)


# Backward compatibility aliases (v1.0 names)
blkp = lookupSecurity
ablkp = alookupSecurity
bport = getPortfolio


def getBlpapiVersion(**kwargs) -> dict[str, str]:
    """Get Bloomberg API version information.

    Retrieves both header and runtime version information for the Bloomberg API.

    Args:
        **kwargs: Infrastructure options (e.g., port, server) - not used but kept for API consistency.

    Returns:
        dict: Dictionary with 'header' and 'runtime' version strings.

    Examples:
        >>> from xbbg import blp
        >>> version = blp.getBlpapiVersion()  # doctest: +SKIP
        >>> print(f"Header: {version['header']}, Runtime: {version['runtime']}")  # doctest: +SKIP
    """
    if not blpapi:
        raise RuntimeError("blpapi is not available")

    try:
        # Try to get version info using blpapi's version functions
        # Note: blpapi Python bindings may expose version differently than C++ API
        header_version = None
        runtime_version = None

        # Try accessing version info if available
        if hasattr(blpapi, "VersionInfo"):
            vi_header = blpapi.VersionInfo.headerVersion()
            header_version = f"{vi_header.majorVersion()}.{vi_header.minorVersion()}.{vi_header.patchVersion()}.{vi_header.buildVersion()}"

            vi_runtime = blpapi.VersionInfo.runtimeVersion()
            runtime_version = f"{vi_runtime.majorVersion()}.{vi_runtime.minorVersion()}.{vi_runtime.patchVersion()}.{vi_runtime.buildVersion()}"
        elif hasattr(blpapi, "__version__"):
            # Fallback to module version if VersionInfo not available
            header_version = getattr(blpapi, "__version__", "unknown")
            runtime_version = header_version
        else:
            # Last resort: try to get version identifier
            try:
                version_id = blpapi.VersionInfo.versionIdentifier()
                header_version = version_id
                runtime_version = version_id
            except (AttributeError, Exception):
                header_version = "unknown"
                runtime_version = "unknown"

        return {
            "header": header_version or "unknown",
            "runtime": runtime_version or "unknown",
        }
    except Exception as e:
        logger.warning("Could not retrieve Bloomberg API version: %s", e)
        return {
            "header": "unknown",
            "runtime": "unknown",
        }
