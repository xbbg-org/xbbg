"""Realtime data API module.

This module provides Bloomberg real-time subscription functionality.
Note: Realtime APIs are async/subscription-based and may not follow the same
pipeline pattern as other APIs.
"""

from xbbg.api.realtime.realtime import live, subscribe

__all__ = ['live', 'subscribe']

