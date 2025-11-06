Docstring Standardization
=========================

This branch tracks the effort to improve and standardize docstrings across the ``xbbg`` package.

Style
-----

- Preferred style: `NumPy Docstring Standard <https://numpydoc.readthedocs.io/en/latest/format.html>`_.
- Rendered via Sphinx (``sphinx.ext.napoleon`` recommended for NumPy-style parsing).

Guidelines
----------

- Include a short summary line in the imperative mood.
- Provide sections as needed: ``Parameters``, ``Returns``, ``Yields``, ``Raises``, ``Notes``, ``Examples``.
- Use explicit types and shapes when helpful; prefer concrete meanings over abbreviations.
- Keep examples runnable when possible.

Scope
-----

- Start with public APIs in ``xbbg.blp`` and ``xbbg.core``; expand to other modules.

Tracking
--------

Progress will be maintained in this branch and summarized in the pull request.


