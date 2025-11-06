Docstring Standardization
=========================

This branch tracks the effort to improve and standardize docstrings across the ``xbbg`` package.

Style
-----

- Preferred style: `Google Python Style Guide (Docstrings) <https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings>`_.
- Rendered via Sphinx with ``sphinx.ext.napoleon`` (Google-style parsing enabled).

Guidelines
----------

- Include a short summary line in the imperative mood.
- Provide sections as needed: ``Args``, ``Returns``, ``Yields``, ``Raises``, ``Notes``, ``Examples``.
- Use explicit types and shapes when helpful; prefer concrete meanings over abbreviations.
- Keep examples runnable when possible.

Scope
-----

- Start with public APIs in ``xbbg.blp`` and ``xbbg.core``; expand to other modules.

Tracking
--------

Progress will be maintained in this branch and summarized in the pull request.


