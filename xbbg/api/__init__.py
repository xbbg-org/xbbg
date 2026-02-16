"""Bloomberg API modules organized by functionality.

This package contains the main Bloomberg API functions organized into logical modules:
- reference: Reference data (BDP/BDS)
- historical: Historical data (BDH, dividends, earnings, turnover)
- intraday: Intraday bars and tick data
- screening: Screening and query functions (BEQS, BSRCH, BQL)
- technical: Technical analysis (BTA)
- realtime: Real-time subscriptions and live data
- helpers: Shared utility functions (currency conversion, etc.)
"""

# Import submodules to make them accessible as attributes (needed for mocking in tests)
from xbbg.api import helpers, historical, intraday, realtime, reference, screening, technical

# Re-export all public functions for convenience
from xbbg.api.helpers import *
from xbbg.api.historical import *
from xbbg.api.intraday import *
from xbbg.api.realtime import *
from xbbg.api.reference import *
from xbbg.api.screening import *
from xbbg.api.technical import *
