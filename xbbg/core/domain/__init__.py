"""Domain model and contracts for Bloomberg data pipeline.

This package contains domain objects and context management:
- contracts: Value Objects and Protocols (domain model)
- context: Bloomberg API context management
"""

# Import modules for easy access
from xbbg.core.domain import context as context_module, contracts as contracts_module

__all__ = ['contracts_module', 'context_module']

