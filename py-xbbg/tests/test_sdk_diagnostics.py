from __future__ import annotations

import importlib
import logging
from pathlib import Path
import sys
from unittest import TestCase
import warnings

_CASE = TestCase()


def test_import_xbbg_is_warning_free():
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        _CASE.assertIsNotNone(importlib.import_module("xbbg"))

    _CASE.assertEqual(recorded, [])


def test_get_lib_version_failure_is_debug_observable(monkeypatch, caplog):
    import xbbg
    from xbbg import _sdk

    def raise_sdk_version():
        raise RuntimeError("boom")

    monkeypatch.setattr(xbbg, "_core", type("FakeCore", (), {"sdk_version": raise_sdk_version})(), raising=False)

    with caplog.at_level(logging.DEBUG, logger="xbbg._sdk"):
        _CASE.assertIsNone(_sdk._get_lib_version(Path("C:/missing/blpapi3_64.dll")))

    _CASE.assertTrue(
        any("Could not determine Bloomberg SDK runtime version" in record.message for record in caplog.records)
    )
    _CASE.assertTrue(any(record.exc_info for record in caplog.records))


def test_get_sdk_info_runtime_failure_is_debug_observable(monkeypatch, caplog):
    import xbbg
    from xbbg import _sdk

    def raise_sdk_version():
        raise RuntimeError("boom")

    monkeypatch.setattr(_sdk, "_sdk_info", None)
    monkeypatch.setattr(xbbg, "_core", type("FakeCore", (), {"sdk_version": raise_sdk_version})(), raising=False)

    with caplog.at_level(logging.DEBUG, logger="xbbg._sdk"):
        info = _sdk.get_sdk_info()

    _CASE.assertIn("runtime_version", info)
    _CASE.assertTrue(
        any("Could not determine Bloomberg SDK runtime version" in record.message for record in caplog.records)
    )
    _CASE.assertTrue(any(record.exc_info for record in caplog.records))


def test_prepare_sdk_failure_is_debug_observable(monkeypatch, caplog):
    from xbbg import _sdk

    def raise_prepare():
        raise RuntimeError("boom")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(_sdk, "_add_sdk_to_dll_search_path", raise_prepare)

    with caplog.at_level(logging.DEBUG, logger="xbbg._sdk"):
        _sdk._prepare_sdk_for_core_import()

    _CASE.assertTrue(any("Failed to prepare Bloomberg SDK" in record.message for record in caplog.records))
    _CASE.assertTrue(any(record.exc_info for record in caplog.records))


def test_set_sdk_path_prepares_manual_sdk(monkeypatch, tmp_path):
    from xbbg import _sdk

    sdk_dir = tmp_path / "sdk"
    sdk_dir.mkdir()
    lib_path = sdk_dir / "blpapi3_64.dll"
    lib_path.write_text("placeholder")
    calls = []

    monkeypatch.setattr(_sdk, "_find_sdk_lib", lambda path: lib_path if path == sdk_dir else None)
    monkeypatch.setattr(_sdk, "_prepare_sdk_for_core_import", lambda: calls.append("prepare"))
    monkeypatch.setattr(_sdk, "_manual_sdk_path", None)
    monkeypatch.setattr(_sdk, "_sdk_info", {"cached": True})

    _sdk.set_sdk_path(sdk_dir)

    _CASE.assertEqual(_sdk._manual_sdk_path, sdk_dir)
    _CASE.assertIsNone(_sdk._sdk_info)
    _CASE.assertEqual(calls, ["prepare"])


def test_windows_dll_directory_handles_are_retained(monkeypatch, tmp_path):
    from xbbg import _sdk

    sdk_dir = tmp_path / "sdk"
    sdk_dir.mkdir()
    lib_path = sdk_dir / "blpapi3_64.dll"
    lib_path.write_text("placeholder")
    import os
    handles = []


    monkeypatch.setattr(_sdk, "_collect_sdk_candidate_dirs", lambda: [sdk_dir])
    monkeypatch.setattr(_sdk, "_find_sdk_lib", lambda path: lib_path if path == sdk_dir else None)
    monkeypatch.setattr(_sdk, "_dll_directory_handles", [])
    monkeypatch.setattr(os, "add_dll_directory", lambda path: handles.append(path) or f"handle:{path}", raising=False)

    _sdk._add_sdk_to_dll_search_path()

    _CASE.assertEqual(handles, [str(sdk_dir)])
    _CASE.assertEqual(_sdk._dll_directory_handles, [f"handle:{sdk_dir}"])


def test_package_prepare_failure_is_debug_observable(monkeypatch, caplog):
    import xbbg
    from xbbg import _sdk

    def raise_prepare():
        raise RuntimeError("boom")

    monkeypatch.setattr(_sdk, "_prepare_sdk_for_core_import", raise_prepare)

    with caplog.at_level(logging.DEBUG, logger="xbbg"):
        importlib.reload(xbbg)

    _CASE.assertTrue(
        any("Failed to prepare Bloomberg SDK for package import" in record.message for record in caplog.records)
    )
    _CASE.assertTrue(any(record.exc_info for record in caplog.records))
