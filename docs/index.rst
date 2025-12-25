.. raw:: html

   <div align="center">
   
   <a href="https://github.com/alpha-xone/xbbg">
   <img src="https://raw.githubusercontent.com/alpha-xone/xbbg/main/docs/xbbg.png" alt="xbbg logo" width="150">
   </a>
   
   <p><b>xbbg: An intuitive Bloomberg API for Python</b></p>
   
   <p>
   <a href="https://pypi.org/project/xbbg/"><img src="https://img.shields.io/pypi/v/xbbg.svg" alt="PyPI version"></a>
   <a href="https://pypi.org/project/xbbg/"><img src="https://img.shields.io/pypi/pyversions/xbbg.svg" alt="Python versions"></a>
   <a href="https://pypi.org/project/xbbg/"><img src="https://img.shields.io/pypi/dm/xbbg" alt="PyPI Downloads"></a>
   <a href="https://gitter.im/xbbg/community"><img src="https://badges.gitter.im/xbbg/community.svg" alt="Gitter"></a>
   </p>
   
   <p>
   <a href="https://www.buymeacoffee.com/Lntx29Oof"><img src="https://img.shields.io/badge/Buy%20Me%20a%20Coffee-1E3A8A?style=plastic&logo=buy-me-a-coffee&logoColor=white" alt="Buy Me a Coffee"></a>
   </p>
   
   <p><b>Quick Links:</b> <a href="https://xbbg.readthedocs.io/">Documentation</a> • <a href="#installation">Installation</a> • <a href="#quickstart">Quickstart</a> • <a href="#examples">Examples</a> • <a href="https://github.com/alpha-xone/xbbg">Source</a> • <a href="https://github.com/alpha-xone/xbbg/issues">Issues</a></p>
   
   </div>

xbbg
====

..
   xbbg:latest-release-start

Latest release: xbbg==0.9.1 (release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.9.1>`_)

..
   xbbg:latest-release-end

Overview
========

xbbg is the **most comprehensive and intuitive Bloomberg API wrapper for Python**, providing a Pythonic interface with Excel-compatible inputs, straightforward intraday bar requests, and real-time subscriptions. All functions return pandas DataFrames for seamless integration with your data workflow.

**Why xbbg?**

- 🎯 **Complete API Coverage**: Reference, historical, intraday bars, tick data, real-time subscriptions, equity screening (BEQS), and BQL support
- 📊 **Excel-Compatible**: Use familiar Excel date formats and field names - no learning curve
- ⚡ **Built-in Caching**: Automatic Parquet-based local storage reduces API calls and speeds up workflows
- 🔧 **Rich Utilities**: Currency conversion, futures/CDX resolvers, exchange-aware market hours, and more
- 🚀 **Modern & Active**: Python 3.10+ support with regular updates and active maintenance
- 💡 **Intuitive Design**: Simple, consistent API (``bdp``, ``bdh``, ``bdib``, etc.) that feels natural to use

See `examples/xbbg_jupyter_examples.ipynb <https://github.com/alpha-xone/xbbg/blob/main/examples/xbbg_jupyter_examples.ipynb>`_ for interactive tutorials and examples.

Why Choose xbbg?
================

xbbg stands out as the most comprehensive and user-friendly Bloomberg API wrapper for Python. Here's how it compares to alternatives:

**Key Advantages:**

- 🎯 **Most Complete API**: Covers reference, historical, intraday, tick, real-time, screening, and BQL
- 📊 **Excel Compatibility**: Use familiar Excel date formats and field names
- ⚡ **Performance**: Built-in Parquet caching reduces API calls and speeds up workflows
- 🔧 **Rich Utilities**: Currency conversion, futures resolvers, and more out of the box
- 🚀 **Modern & Active**: Python 3.10+ support with regular updates and active maintenance
- 💡 **Intuitive Design**: Simple, consistent API that feels natural to use

Requirements
============

- Bloomberg C++ SDK version 3.12.1 or higher

    - Visit `Bloomberg API Library`_ and download C++ Supported Release

    - In the ``bin`` folder of downloaded zip file, copy ``blpapi3_32.dll`` and ``blpapi3_64.dll`` to Bloomberg ``BLPAPI_ROOT`` folder (usually ``blp/DAPI``)

- Bloomberg official Python API:

.. code-block:: console

   pip install blpapi --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/

- numpy, pandas, ruamel.yaml and pyarrow

Installation
============

.. code-block:: console

   pip install xbbg

Supported Python versions: 3.10 – 3.14 (universal wheel)

Supported Functionality
========================

xbbg provides comprehensive Bloomberg API coverage:

**Reference Data:**
- ``bdp()`` - Single point-in-time reference data
- ``bds()`` - Bulk/block data (multi-row)

**Historical Data:**
- ``bdh()`` - End-of-day historical data
- ``dividend()`` - Dividend & split history
- ``earning()`` - Corporate earnings breakdowns
- ``turnover()`` - Trading volume & turnover

**Intraday Data:**
- ``bdib()`` - Intraday bar data
- ``bdtick()`` - Tick-by-tick data

**Screening & Queries:**
- ``beqs()`` - Bloomberg Equity Screening
- ``bql()`` - Bloomberg Query Language

**Real-time:**
- ``live()`` - Real-time market data
- ``subscribe()`` - Real-time subscriptions

**Utilities:**
- ``adjust_ccy()`` - Currency conversion
- ``active_futures()`` - Active futures contracts
- ``fut_ticker()`` - Futures ticker resolution
- ``cdx_ticker()`` - CDX index ticker resolution
- ``active_cdx()`` - Active CDX contracts

**Additional Features**: Local caching (Parquet), configurable logging, timezone support, exchange-aware market hours, batch processing, standardized column mapping

Quickstart
==========

.. code-block:: python

   from xbbg import blp

   # Reference data (BDP)
   ref = blp.bdp(tickers='AAPL US Equity', flds=['Security_Name', 'GICS_Sector_Name'])
   print(ref)

   # Historical data (BDH)
   hist = blp.bdh('SPX Index', ['high', 'low', 'last_price'], '2021-01-01', '2021-01-05')
   print(hist.tail())

What's New
==========

.. xbbg:changelog-start

*0.9.1* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.9.1>`__

## What's Changed

- fix: Fix BQL returning only one row for multi-value results by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/152

- fix(docs): add blank lines around latest-release markers in index.rst

- ci: remove redundant release triggers from workflows

- ci: trigger release workflows explicitly from semantic_version

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.9.0...v0.9.1


*0.9.0* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.9.0>`__

## What's Changed

- feat: Add etf_holdings() function for retrieving ETF holdings via BQL by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/147

- feat: Add multi-day support to bdib() by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/148

- feat: Add multi-day cache support for bdib() by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/149

- fix: resolve RST duplicate link targets and Sphinx build warnings

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.8.2...v0.9.0


*0.8.2* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.8.2>`__

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.8.1...v0.8.2

## What's Changed

- Fix BQL options chain metadata issues by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/146

*0.8.1* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.8.1>`__

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.8.0...v0.8.1

*0.8.0* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.8.0>`__

**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.7.11...v0.8.0

## What's Changed
* Improved logging with blpapi integration and performance optimizations by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/135
* feat: add fixed income securities support to bdib by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/136
* feat: add interval parameter to subscribe() and live() functions by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/132
* fix(beqs): increase timeout and max_timeouts for BEQS requests by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/133
* feat: add bsrch() function for Bloomberg SRCH queries (Excel =@BSRCH equivalent) by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/137
* feat: add server host parameter support to connect_bbg() by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/138
* fix: remove 1-minute offset for bare session names in bdtick by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/139
* fix(issue-68): Add support for GY (Xetra), IM (Borsa Italiana), and SE (SIX) exchanges by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/140
* Fix BQL syntax documentation and error handling (Fixes #141) by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/142
* refactor: comprehensive codebase cleanup and restructuring by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/144


*0.7.10* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.7.10>`__

## What's Changed

* Migrate to uv + PEP 621; modernize CI and blpapi index by @kaijensen55 in https://github.com/alpha-xone/xbbg/pull/124



## New Contributors

* @kaijensen55 made their first contribution in https://github.com/alpha-xone/xbbg/pull/124



**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.7.9...v0.7.10

*0.7.11* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.7.11>`__

## What's Changed

* ci: use uv build in publish workflows by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/125

* docs: standardize docstrings (Google) + Ruff/napoleon config by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/127

* feat: BQL support + CI workflow improvements (uv venv) by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/128

* feat(bdib): add support for sub-minute intervals via intervalHasSeconds flag by @kj55-dev in https://github.com/alpha-xone/xbbg/pull/131



**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.7.10...v0.7.11

*0.7.9* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.7.9>`__

## What's Changed

* Fixing typo in TLS Options when creating a new connection by @rchiorean in https://github.com/alpha-xone/xbbg/pull/110

* Fixing Auto CI by @rchiorean in https://github.com/alpha-xone/xbbg/pull/111



## New Contributors

* @rchiorean made their first contribution in https://github.com/alpha-xone/xbbg/pull/110



**Full Changelog**: https://github.com/alpha-xone/xbbg/compare/v0.7.7...v0.7.9

*0.7.8a2* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.7.8a2>`__

*0.7.7* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.7.7>`__

*0.7.7a4* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.7.7a4>`__

*0.7.7a3* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.7.7a3>`__

*0.7.7a2* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.7.7a2>`__

*0.7.7a1* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.7.7a1>`__

*0.7.6* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.7.6>`__

*0.7.6a8* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.7.6a8>`__

*0.7.6a7* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.7.6a7>`__

*0.7.6a6* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.7.6a6>`__

*0.7.6a5* - see release: `notes <https://github.com/alpha-xone/xbbg/releases/tag/v0.7.6a5>`__
.. xbbg:changelog-end

*0.7.2* - Use `async` for live data feeds

*0.7.0* - ``bdh`` preserves columns orders (both tickers and flds).
``timeout`` argument is available for all queries - ``bdtick`` usually takes longer to respond -
can use ``timeout=1000`` for example if keep getting empty DataFrame.

*0.6.6* - Add flexibility to use reference exchange as market hour definition
(so that it's not necessary to add ``.yml`` for new tickers, provided that the exchange was defined
in ``/xbbg/markets/exch.yml``). See example of ``bdib`` below for more details.

*0.6.0* - Speed improvements and tick data availablity

*0.5.0* - Rewritten library to add subscription, BEQS, simplify interface and remove dependency of `pdblp`

*0.1.22* - Remove PyYAML dependency due to security vulnerability

*0.1.17* - Add ``adjust`` argument in ``bdh`` for easier dividend / split adjustments

Contents
========

.. toctree::
   :maxdepth: 1

   docstring_style

Tutorial
========

.. code-block:: python

    In [1]: from xbbg import blp

Basics
------

``BDP`` example:

.. code-block:: python

    In [2]: blp.bdp(tickers='NVDA US Equity', flds=['Security_Name', 'GICS_Sector_Name'])
    Out[2]:
                   security_name        gics_sector_name
    NVDA US Equity   NVIDIA Corp  Information Technology

``BDP`` with overrides:

.. code-block:: python

    In [3]: blp.bdp('AAPL US Equity', 'Eqy_Weighted_Avg_Px', VWAP_Dt='20181224')
    Out[3]:
                    eqy_weighted_avg_px
    AAPL US Equity               148.75

``BDH`` example:

.. code-block:: python

    In [4]: blp.bdh(
       ...:     tickers='SPX Index', flds=['High', 'Low', 'Last_Price'],
       ...:     start_date='2018-10-10', end_date='2018-10-20',
       ...: )
    Out[4]:
               SPX Index
                    High      Low Last_Price
    2018-10-10  2,874.02 2,784.86   2,785.68
    2018-10-11  2,795.14 2,710.51   2,728.37
    2018-10-12  2,775.77 2,729.44   2,767.13
    2018-10-15  2,775.99 2,749.03   2,750.79
    2018-10-16  2,813.46 2,766.91   2,809.92
    2018-10-17  2,816.94 2,781.81   2,809.21
    2018-10-18  2,806.04 2,755.18   2,768.78
    2018-10-19  2,797.77 2,760.27   2,767.78

``BDH`` example with Excel compatible inputs:

.. code-block:: python

    In [5]: blp.bdh(
       ...:     tickers='SHCOMP Index', flds=['High', 'Low', 'Last_Price'],
       ...:     start_date='2018-09-26', end_date='2018-10-20',
       ...:     Per='W', Fill='P', Days='A',
       ...: )
    Out[5]:
               SHCOMP Index
                       High      Low Last_Price
    2018-09-28     2,827.34 2,771.16   2,821.35
    2018-10-05     2,827.34 2,771.16   2,821.35
    2018-10-12     2,771.94 2,536.66   2,606.91
    2018-10-19     2,611.97 2,449.20   2,550.47

``BDH`` without adjustment for dividends and splits:

.. code-block:: python

    In [6]: blp.bdh(
       ...:     'AAPL US Equity', 'Px_Last', '20140605', '20140610',
       ...:     CshAdjNormal=False, CshAdjAbnormal=False, CapChg=False
       ...: )
    Out[6]:
               AAPL US Equity
                      Px_Last
    2014-06-05         647.35
    2014-06-06         645.57
    2014-06-09          93.70
    2014-06-10          94.25

``BDH`` adjusted for dividends and splits:

.. code-block:: python

    In [7]: blp.bdh(
       ...:     'AAPL US Equity', 'Px_Last', '20140605', '20140610',
       ...:     CshAdjNormal=True, CshAdjAbnormal=True, CapChg=True
       ...: )
    Out[7]:
               AAPL US Equity
                      Px_Last
    2014-06-05          85.45
    2014-06-06          85.22
    2014-06-09          86.58
    2014-06-10          87.09

``BDS`` example:

.. code-block:: python

    In [8]: blp.bds('AAPL US Equity', 'DVD_Hist_All', DVD_Start_Dt='20180101', DVD_End_Dt='20180531')
    Out[8]:
                   declared_date     ex_date record_date payable_date  dividend_amount dividend_frequency dividend_type
    AAPL US Equity    2018-05-01  2018-05-11  2018-05-14   2018-05-17             0.73            Quarter  Regular Cash
    AAPL US Equity    2018-02-01  2018-02-09  2018-02-12   2018-02-15             0.63            Quarter  Regular Cash

Intraday bars ``BDIB`` example:

.. code-block:: python

    In [9]: blp.bdib(ticker='BHP AU Equity', dt='2018-10-17').tail()
    Out[9]:
                              BHP AU Equity
                                       open  high   low close   volume num_trds
    2018-10-17 15:56:00+11:00         33.62 33.65 33.62 33.64    16660      126
    2018-10-17 15:57:00+11:00         33.65 33.65 33.63 33.64    13875      156
    2018-10-17 15:58:00+11:00         33.64 33.65 33.62 33.63    16244      159
    2018-10-17 15:59:00+11:00         33.63 33.63 33.61 33.62    16507      167
    2018-10-17 16:10:00+11:00         33.66 33.66 33.66 33.66  1115523      216

Above example works because 1) ``AU`` in equity ticker is mapped to ``EquityAustralia`` in
``markets/assets.yml``, and 2) ``EquityAustralia`` is defined in ``markets/exch.yml``.
To add new mappings, define ``BBG_ROOT`` in sys path and add ``assets.yml`` and
``exch.yml`` under ``BBG_ROOT/markets``.

*New in 0.6.6* - if exchange is defined in ``/xbbg/markets/exch.yml``, can use ``ref`` to look for
relevant exchange market hours. Both ``ref='ES1 Index'`` and ``ref='CME'`` work for this example:

.. code-block:: python

    In [10]: blp.bdib(ticker='ESM0 Index', dt='2020-03-20', ref='ES1 Index').tail()
    out[10]:
                              ESM0 Index
                                    open     high      low    close volume num_trds        value
    2020-03-20 16:55:00-04:00   2,260.75 2,262.25 2,260.50 2,262.00    412      157   931,767.00
    2020-03-20 16:56:00-04:00   2,262.25 2,267.00 2,261.50 2,266.75    812      209 1,838,823.50
    2020-03-20 16:57:00-04:00   2,266.75 2,270.00 2,264.50 2,269.00   1136      340 2,576,590.25
    2020-03-20 16:58:00-04:00   2,269.25 2,269.50 2,261.25 2,265.75   1077      408 2,439,276.00
    2020-03-20 16:59:00-04:00   2,265.25 2,272.00 2,265.00 2,266.50   1271      378 2,882,978.25

Intraday bars within market session:

.. code-block:: python

    In [11]: blp.bdib(ticker='7974 JT Equity', dt='2018-10-17', session='am_open_30').tail()
    Out[11]:
                              7974 JT Equity
                                        open      high       low     close volume num_trds
    2018-10-17 09:27:00+09:00      39,970.00 40,020.00 39,970.00 39,990.00  10800       44
    2018-10-17 09:28:00+09:00      39,990.00 40,020.00 39,980.00 39,980.00   6300       33
    2018-10-17 09:29:00+09:00      39,970.00 40,000.00 39,960.00 39,970.00   3300       21
    2018-10-17 09:30:00+09:00      39,960.00 40,010.00 39,950.00 40,000.00   3100       19
    2018-10-17 09:31:00+09:00      39,990.00 40,000.00 39,980.00 39,990.00   2000       15

Corporate earnings:

.. code-block:: python

    In [12]: blp.earning('AMD US Equity', by='Geo', Eqy_Fund_Year=2017, Number_Of_Periods=1)
    Out[12]:
                     level    fy2017  fy2017_pct
    Asia-Pacific      1.00  3,540.00       66.43
        China         2.00  1,747.00       49.35
        Japan         2.00  1,242.00       35.08
        Singapore     2.00    551.00       15.56
    United States     1.00  1,364.00       25.60
    Europe            1.00    263.00        4.94
    Other Countries   1.00    162.00        3.04

Dividends:

.. code-block:: python

    In [13]: blp.dividend(['C US Equity', 'MS US Equity'], start_date='2018-01-01', end_date='2018-05-01')
    Out[13]:
                    dec_date     ex_date    rec_date    pay_date  dvd_amt dvd_freq      dvd_type
    C US Equity   2018-01-18  2018-02-02  2018-02-05  2018-02-23     0.32  Quarter  Regular Cash
    MS US Equity  2018-04-18  2018-04-27  2018-04-30  2018-05-15     0.25  Quarter  Regular Cash
    MS US Equity  2018-01-18  2018-01-30  2018-01-31  2018-02-15     0.25  Quarter  Regular Cash

-----

*New in 0.1.17* - Dividend adjustment can be simplified to one parameter ``adjust``:

- ``BDH`` without adjustment for dividends and splits:

.. code-block:: python

    In [14]: blp.bdh('AAPL US Equity', 'Px_Last', '20140606', '20140609', adjust='-')
    Out[14]:
               AAPL US Equity
                      Px_Last
    2014-06-06         645.57
    2014-06-09          93.70

- ``BDH`` adjusted for dividends and splits:

.. code-block:: python

    In [15]: blp.bdh('AAPL US Equity', 'Px_Last', '20140606', '20140609', adjust='all')
    Out[15]:
               AAPL US Equity
                      Px_Last
    2014-06-06          85.22
    2014-06-09          86.58

Data Storage
------------

If ``BBG_ROOT`` is provided in ``os.environ``, data can be saved locally in Parquet format.
By default, local storage is preferred over Bloomberg for all queries.

**Important**: Local data usage must be compliant with Bloomberg Datafeed Addendum
(full description in ``DAPI<GO>``):

    To access Bloomberg data via the API (and use that data in Microsoft Excel),
    your company must sign the 'Datafeed Addendum' to the Bloomberg Agreement.
    This legally binding contract describes the terms and conditions of your use
    of the data and information available via the API (the "Data").
    The most fundamental requirement regarding your use of Data is that it cannot
    leave the local PC you use to access the BLOOMBERG PROFESSIONAL service.

Development
===========

Setup
-----

Create venv and install dependencies:

.. code-block:: console

   uv venv .venv
   .\.venv\Scripts\Activate.ps1
   uv sync --locked --extra dev --extra test

Adding Dependencies
--------------------

.. code-block:: console

   uv add <package>

Running Tests and Linting
--------------------------

.. code-block:: console

   uv run ruff check xbbg
   uv run pytest --doctest-modules --cov -v xbbg

Building
--------

.. code-block:: console

   uv run python -m build

Publishing is handled via GitHub Actions using PyPI Trusted Publishing (OIDC).

Documentation
-------------

.. code-block:: console

   uv sync --locked --extra docs
   uv run sphinx-build -b html docs docs/_build/html

Contributing
============

- Issues and feature requests: please open an issue on the repository.
- Pull requests welcome. Run lint and tests locally:

.. code-block:: console

   uv sync --locked --extra dev --extra test
   uv run ruff check xbbg
   uv run pytest --doctest-modules -q

Links
=====

- `PyPI <https://pypi.org/project/xbbg/>`_
- `Documentation <https://xbbg.readthedocs.io/>`_
- `Source <https://github.com/alpha-xone/xbbg>`_
- Security policy: see ``SECURITY.md``

============== ======================
Docs           |docs|
Build          |actions|
Coverage       |codecov|
Quality        |codacy|
\              |codeFactor|
\              |codebeat|
License        |license|
============== ======================

.. |pypi| image:: https://img.shields.io/pypi/v/xbbg.svg
    :target: https://pypi.org/project/xbbg/
.. |version| image:: https://img.shields.io/pypi/pyversions/xbbg.svg
    :target: https://pypi.org/project/xbbg/
.. |actions| image:: https://github.com/alpha-xone/xbbg/workflows/Auto%20CI/badge.svg
    :target: https://github.com/alpha-xone/xbbg/actions
    :alt: Travis CI
.. |codecov| image:: https://codecov.io/gh/alpha-xone/xbbg/branch/main/graph/badge.svg
    :target: https://codecov.io/gh/alpha-xone/xbbg
    :alt: Codecov
.. |docs| image:: https://readthedocs.org/projects/xbbg/badge/?version=latest
    :target: https://xbbg.readthedocs.io/
.. |codefactor| image:: https://www.codefactor.io/repository/github/alpha-xone/xbbg/badge
   :target: https://www.codefactor.io/repository/github/alpha-xone/xbbg
   :alt: CodeFactor
.. |codacy| image:: https://app.codacy.com/project/badge/Grade/daec9f52ba344e3ea116c15f1fc6d541
   :target: https://www.codacy.com/gh/alpha-xone/xbbg
.. |codebeat| image:: https://codebeat.co/badges/eef1f14d-72eb-445a-af53-12d3565385ec
   :target: https://codebeat.co/projects/github-com-alpha-xone-xbbg-main
.. |license| image:: https://img.shields.io/github/license/alpha-xone/xbbg.svg
    :alt: GitHub license
    :target: https://github.com/alpha-xone/xbbg/blob/main/LICENSE
.. |chat| image:: https://badges.gitter.im/xbbg/community.svg
   :target: https://gitter.im/xbbg/community
.. |download| image:: https://img.shields.io/pypi/dm/xbbg
   :target: https://pypistats.org/packages/xbbg
.. |coffee| image:: https://img.shields.io/badge/Buy%20Me%20a%20Coffee-1E3A8A?style=plastic&logo=buy-me-a-coffee&logoColor=white
   :target: https://www.buymeacoffee.com/Lntx29Oof
   :alt: Buy Me a Coffee
.. _Bloomberg API Library: https://www.bloomberg.com/professional/support/api-library/
