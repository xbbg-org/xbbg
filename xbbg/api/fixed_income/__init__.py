"""Bloomberg Fixed Income API.

Provides convenience functions for fixed income analytics including
yield and spread analysis (YAS).
"""

from xbbg.api.fixed_income.yas import YieldType, yas

__all__ = ["yas", "YieldType"]
