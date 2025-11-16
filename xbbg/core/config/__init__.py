"""Bloomberg API configuration utilities.

This package contains Bloomberg-specific configuration:
- overrides: Bloomberg override and element option processing
- intervals: Trading session interval resolution
"""

# Import modules for easy access
from xbbg.core.config import intervals as intervals_module, overrides as overrides_module

__all__ = ['intervals_module', 'overrides_module']

