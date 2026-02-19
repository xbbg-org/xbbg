"""Session derivation from Bloomberg exchange metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from xbbg._core import ext_derive_sessions

if TYPE_CHECKING:
    from xbbg.markets.bloomberg import ExchangeInfo


@dataclass
class SessionWindows:
    """Trading session windows for a security."""

    day: tuple[str, str] | None = None
    allday: tuple[str, str] | None = None
    pre: tuple[str, str] | None = None
    post: tuple[str, str] | None = None
    am: tuple[str, str] | None = None
    pm: tuple[str, str] | None = None

    def to_dict(self) -> dict[str, tuple[str, str]]:
        """Convert to dict, excluding None values."""
        result: dict[str, tuple[str, str]] = {}
        if self.day:
            result["day"] = self.day
        if self.allday:
            result["allday"] = self.allday
        if self.pre:
            result["pre"] = self.pre
        if self.post:
            result["post"] = self.post
        if self.am:
            result["am"] = self.am
        if self.pm:
            result["pm"] = self.pm
        return result


def derive_sessions(exchange_info: ExchangeInfo) -> SessionWindows:
    """Derive session windows from ExchangeInfo using Rust market rules."""
    regular = exchange_info.sessions.get("regular")
    futures = exchange_info.sessions.get("futures")
    base_session = regular or futures
    if not base_session:
        return SessionWindows()

    values = ext_derive_sessions(
        day_start=base_session[0],
        day_end=base_session[1],
        mic=exchange_info.mic,
        exch_code=exchange_info.exch_code,
    )
    return SessionWindows(
        day=values.get("day"),
        allday=values.get("allday"),
        pre=values.get("pre"),
        post=values.get("post"),
        am=values.get("am"),
        pm=values.get("pm"),
    )


def get_session_windows(
    ticker: str,
    mic: str | None = None,
    exch_code: str | None = None,
    regular_hours: tuple[str, str] | None = None,
) -> SessionWindows:
    """Convenience helper to derive sessions without a Bloomberg query."""
    from xbbg.markets.bloomberg import ExchangeInfo

    sessions: dict[str, tuple[str, str]] = {}
    if regular_hours:
        sessions["regular"] = regular_hours

    info = ExchangeInfo(ticker=ticker, mic=mic, exch_code=exch_code, sessions=sessions)
    return derive_sessions(info)
