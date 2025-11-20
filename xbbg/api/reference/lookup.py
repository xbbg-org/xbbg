"""Bloomberg lookup and utility functions.

Provides functions for field information, field search, security lookup, and portfolio queries.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from xbbg.core.infra import conn as conn_module
from xbbg.core.infra.blpapi_wrapper import blpapi
from xbbg.core.utils import utils

logger = logging.getLogger(__name__)

__all__ = ['fieldInfo', 'fieldSearch', 'lookupSecurity', 'getPortfolio', 'getBlpapiVersion']


def fieldInfo(fields: str | list[str], **kwargs) -> pd.DataFrame:
    """Get metadata about Bloomberg fields.

    Retrieves field information including ID, mnemonic, data type, and field type
    for the specified Bloomberg fields.

    Args:
        fields: Single field or list of fields to query.
        **kwargs: Infrastructure options (e.g., port, server).

    Returns:
        pd.DataFrame: Field information with columns: id, mnemonic, datatype, ftype.

    Examples:
        >>> from xbbg import blp
        >>> # Get info for single field
        >>> info = blp.fieldInfo('PX_LAST')  # doctest: +SKIP
        >>> # Get info for multiple fields
        >>> info = blp.fieldInfo(['PX_LAST', 'VOLUME'])  # doctest: +SKIP
    """
    field_list = utils.normalize_flds(fields)
    session = conn_module.bbg_session(**kwargs)

    # Open field info service
    service_name = '//blp/apiflds'
    if not session.openService(service_name):
        raise RuntimeError(f'Failed to open {service_name}')

    field_info_service = session.getService(service_name)

    results = []
    for field in field_list:
        # Create FieldInfoRequest
        request = field_info_service.createRequest('FieldInfoRequest')
        request.append(blpapi.Name('id'), field)
        request.set(blpapi.Name('returnFieldDocumentation'), False)

        session.sendRequest(request)

        # Process response
        field_info = None
        while True:
            event = session.nextEvent()
            if event.eventType() not in (blpapi.Event.RESPONSE, blpapi.Event.PARTIAL_RESPONSE):
                continue

            for msg in event:
                field_data = msg.getElement(blpapi.Name('fieldData'))

                if field_data.numValues() > 1:
                    raise ValueError(f'getFieldType: too many fields returned for {field}')

                field_elem = field_data.getValueAsElement(0)

                if field_elem.hasElement(blpapi.Name('fieldError')):
                    error_msg = field_elem.getElement(blpapi.Name('fieldError')).getElementAsString(
                        blpapi.Name('message')
                    )
                    raise ValueError(f'Bad field {field}: {error_msg}')

                # Extract field info
                field_id = field_elem.getElementAsString(blpapi.Name('id'))
                field_info_elem = field_elem.getElement(blpapi.Name('fieldInfo'))
                mnemonic = field_info_elem.getElementAsString(blpapi.Name('mnemonic'))
                datatype = field_info_elem.getElementAsString(blpapi.Name('datatype'))
                ftype = field_info_elem.getElementAsString(blpapi.Name('ftype'))

                field_info = {
                    'id': field_id,
                    'mnemonic': mnemonic,
                    'datatype': datatype,
                    'ftype': ftype,
                }

            if event.eventType() == blpapi.Event.RESPONSE:
                break

        if field_info:
            results.append(field_info)

    return pd.DataFrame(results)


def fieldSearch(searchterm: str, **kwargs) -> pd.DataFrame:
    """Search for Bloomberg fields by name or description.

    Searches for Bloomberg fields matching the given search term. Useful for
    discovering fields when you know what you want but not the exact field name.

    Args:
        searchterm: Search term to match against field names/descriptions.
        **kwargs: Infrastructure options (e.g., port, server).

    Returns:
        pd.DataFrame: Matching fields with columns: id, mnemonic, description.

    Examples:
        >>> from xbbg import blp
        >>> # Search for VWAP-related fields
        >>> results = blp.fieldSearch('vwap')  # doctest: +SKIP
        >>> # Search for volume fields
        >>> results = blp.fieldSearch('volume')  # doctest: +SKIP
    """
    session = conn_module.bbg_session(**kwargs)

    # Open field info service
    service_name = '//blp/apiflds'
    if not session.openService(service_name):
        raise RuntimeError(f'Failed to open {service_name}')

    field_info_service = session.getService(service_name)

    # Create FieldSearchRequest
    request = field_info_service.createRequest('FieldSearchRequest')
    request.set(blpapi.Name('searchSpec'), searchterm)
    request.set(blpapi.Name('returnFieldDocumentation'), False)

    session.sendRequest(request)

    # Process response
    field_ids = []
    mnemonics = []
    descriptions = []

    while True:
        event = session.nextEvent()
        if event.eventType() not in (blpapi.Event.RESPONSE, blpapi.Event.PARTIAL_RESPONSE):
            continue

        for msg in event:
            field_data = msg.getElement(blpapi.Name('fieldData'))

            num_elements = field_data.numValues()
            for i in range(num_elements):
                field_elem = field_data.getValueAsElement(i)
                field_id = field_elem.getElementAsString(blpapi.Name('id'))

                if field_elem.hasElement(blpapi.Name('fieldInfo')):
                    field_info = field_elem.getElement(blpapi.Name('fieldInfo'))
                    mnemonic = field_info.getElementAsString(blpapi.Name('mnemonic'))
                    description = field_info.getElementAsString(blpapi.Name('description'))

                    field_ids.append(field_id)
                    mnemonics.append(mnemonic)
                    descriptions.append(description)
                else:
                    # Field error
                    field_error = field_elem.getElement(blpapi.Name('fieldError'))
                    error_msg = field_error.getElementAsString(blpapi.Name('message'))
                    raise ValueError(f'Field error for {field_id}: {error_msg}')

        if event.eventType() == blpapi.Event.RESPONSE:
            break

    return pd.DataFrame({
        'id': field_ids,
        'mnemonic': mnemonics,
        'description': descriptions,
    })


def lookupSecurity(
    query: str,
    yellowkey: str = 'none',
    language: str = 'none',
    max_results: int = 20,
    verbose: bool = False,
    **kwargs,
) -> pd.DataFrame:
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
        **kwargs: Infrastructure options (e.g., port, server).

    Returns:
        pd.DataFrame: Matching securities with columns: security, description.

    Examples:
        >>> from xbbg import blp
        >>> # Search for IBM
        >>> results = blp.lookupSecurity('IBM')  # doctest: +SKIP
        >>> # Search with asset class filter
        >>> results = blp.lookupSecurity('IBM', yellowkey='eqty')  # doctest: +SKIP
        >>> # Increase max results
        >>> results = blp.lookupSecurity('Apple', max_results=100)  # doctest: +SKIP
    """
    session = conn_module.bbg_session(**kwargs)

    # Open instruments service
    service_name = '//blp/instruments'
    if not session.openService(service_name):
        raise RuntimeError(f'Failed to open {service_name}')

    instruments_service = session.getService(service_name)

    # Map yellowkey to Bloomberg format
    yellowkey_map = {
        'none': 'YK_FILTER_NONE',
        'cmdt': 'YK_FILTER_CMDT',
        'eqty': 'YK_FILTER_EQTY',
        'muni': 'YK_FILTER_MUNI',
        'prfd': 'YK_FILTER_PRFD',
        'clnt': 'YK_FILTER_CLNT',
        'mmkt': 'YK_FILTER_MMKT',
        'govt': 'YK_FILTER_GOVT',
        'corp': 'YK_FILTER_CORP',
        'indx': 'YK_FILTER_INDX',
        'curr': 'YK_FILTER_CURR',
        'mtge': 'YK_FILTER_MTGE',
    }
    yellowkey_filter = yellowkey_map.get(yellowkey.lower(), 'YK_FILTER_NONE')

    # Map language to Bloomberg format
    language_map = {
        'none': 'LANG_OVERRIDE_NONE',
        'english': 'LANG_OVERRIDE_ENGLISH',
        'kanji': 'LANG_OVERRIDE_KANJI',
        'french': 'LANG_OVERRIDE_FRENCH',
        'german': 'LANG_OVERRIDE_GERMAN',
        'spanish': 'LANG_OVERRIDE_SPANISH',
        'portuguese': 'LANG_OVERRIDE_PORTUGUESE',
        'italian': 'LANG_OVERRIDE_ITALIAN',
        'chinese_trad': 'LANG_OVERRIDE_CHINESE_TRAD',
        'korean': 'LANG_OVERRIDE_KOREAN',
        'chinese_simp': 'LANG_OVERRIDE_CHINESE_SIMP',
        'russian': 'LANG_OVERRIDE_RUSSIAN',
    }
    language_override = language_map.get(language.lower(), 'LANG_OVERRIDE_NONE')

    if max_results > 1000:
        logger.warning('max_results may be limited to 1000 by the Bloomberg API')

    # Create instrumentListRequest
    request = instruments_service.createRequest('instrumentListRequest')
    request.set(blpapi.Name('query'), query)
    request.set(blpapi.Name('yellowKeyFilter'), yellowkey_filter)
    request.set(blpapi.Name('languageOverride'), language_override)
    request.set(blpapi.Name('maxResults'), max_results)

    if verbose:
        logger.info(f'Sending lookup request: {request}')

    session.sendRequest(request)

    # Process response
    securities = []
    descriptions = []

    done = False
    while not done:
        event = session.nextEvent()

        if event.eventType() == blpapi.Event.PARTIAL_RESPONSE:
            if verbose:
                logger.debug('Processing partial response')
            _process_lookup_event(event, securities, descriptions, verbose)
        elif event.eventType() == blpapi.Event.RESPONSE:
            if verbose:
                logger.debug('Processing response')
            _process_lookup_event(event, securities, descriptions, verbose)
            done = True
        elif event.eventType() == blpapi.Event.SESSION_STATUS:
            for msg in event:
                if msg.messageType() == blpapi.Name('SessionTerminated'):
                    done = True

    return pd.DataFrame({
        'security': securities,
        'description': descriptions,
    })


def _process_lookup_event(
    event: blpapi.Event,
    securities: list[str],
    descriptions: list[str],
    verbose: bool,
) -> None:
    """Process lookup response event."""
    for msg in event:

        if msg.hasElement(blpapi.Name('responseError')):
            error_msg = msg.getElement(blpapi.Name('responseError'))
            logger.error(f'REQUEST FAILED: {error_msg}')
            continue

        response = msg.asElement()
        if str(response.name()) != 'InstrumentListResponse':
            raise ValueError('Not a valid InstrumentListResponse')

        results = response.getElement(blpapi.Name('results'))
        num_items = results.numValues()

        if verbose:
            logger.debug(f'Response contains {num_items} items')

        for i in range(num_items):
            item = results.getValueAsElement(i)
            security = item.getElementAsString(blpapi.Name('security'))
            description = item.getElementAsString(blpapi.Name('description'))

            if verbose:
                logger.debug(f'{security}\t\t{description}')

            securities.append(security)
            descriptions.append(description)


def getPortfolio(
    security: str,
    field: str,
    options: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
    verbose: bool = False,
    **kwargs,
) -> pd.DataFrame:
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
        **kwargs: Additional infrastructure options.

    Returns:
        pd.DataFrame: Portfolio data.

    Examples:
        >>> from xbbg import blp
        >>> # Get portfolio data
        >>> portfolio = blp.getPortfolio('PORTFOLIO_NAME', 'PORTFOLIO_MWEIGHT')  # doctest: +SKIP
    """
    from xbbg.api.reference.reference import bds

    # Merge options and overrides into kwargs
    all_kwargs = {**kwargs}
    if options:
        all_kwargs.update(options)
    if overrides:
        all_kwargs.update(overrides)

    return bds(security, field, use_port=True, verbose=verbose, **all_kwargs)


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
        raise RuntimeError('blpapi is not available')

    try:
        # Try to get version info using blpapi's version functions
        # Note: blpapi Python bindings may expose version differently than C++ API
        header_version = None
        runtime_version = None

        # Try accessing version info if available
        if hasattr(blpapi, 'VersionInfo'):
            vi_header = blpapi.VersionInfo.headerVersion()
            header_version = f'{vi_header.majorVersion()}.{vi_header.minorVersion()}.{vi_header.patchVersion()}.{vi_header.buildVersion()}'

            vi_runtime = blpapi.VersionInfo.runtimeVersion()
            runtime_version = f'{vi_runtime.majorVersion()}.{vi_runtime.minorVersion()}.{vi_runtime.patchVersion()}.{vi_runtime.buildVersion()}'
        elif hasattr(blpapi, '__version__'):
            # Fallback to module version if VersionInfo not available
            header_version = getattr(blpapi, '__version__', 'unknown')
            runtime_version = header_version
        else:
            # Last resort: try to get version identifier
            try:
                version_id = blpapi.VersionInfo.versionIdentifier()
                header_version = version_id
                runtime_version = version_id
            except (AttributeError, Exception):
                header_version = 'unknown'
                runtime_version = 'unknown'

        return {
            'header': header_version or 'unknown',
            'runtime': runtime_version or 'unknown',
        }
    except Exception as e:
        logger.warning('Could not retrieve Bloomberg API version: %s', e)
        return {
            'header': 'unknown',
            'runtime': 'unknown',
        }

