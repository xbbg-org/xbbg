# Bloomberg BLPAPI SDK (Windows) - Local Development Only

This directory is intentionally ignored by git. Place the Bloomberg API Windows ZIP (and/or the extracted SDK) here for local development and testing. Do not commit any SDK files.

Download (C++ Supported Release):
- API Windows from the Bloomberg API Library page: https://www.bloomberg.com/professional/support/api-library/

Suggested layout after download:

- vendor/blpapi/
  - blpapi-windows.zip            (ZIP you downloaded)
  - blpapi_cpp/                   (extracted C++ SDK: include/, lib/, etc.)

Environment hints (optional):
- Set BLPAPI_SDK_DIR to the extracted SDK root (e.g., vendor/blpapi/blpapi_cpp)
- For build tools that need the SDK explicitly, configure include and lib paths accordingly.

Note:
- The official Python wheels for `blpapi` already bundle the C++ API for supported Python versions and platforms. Use the SDK here only if you need to build from source or run C++-based tooling.


