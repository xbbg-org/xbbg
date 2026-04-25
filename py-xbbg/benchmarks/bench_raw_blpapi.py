"""Raw blpapi profiled benchmark — phase-level timing comparison with Rust."""

from __future__ import annotations

import logging
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import blpapi

logger = logging.getLogger(__name__)


def main():
    logger.info("Raw blpapi Profiled BDP Benchmark")
    logger.info("=" * 40)

    # Setup session
    options = blpapi.SessionOptions()
    options.setServerHost("127.0.0.1")
    options.setServerPort(8194)

    session = blpapi.Session(options)

    t = time.perf_counter()
    session.start()
    logger.info(f"Session start: {(time.perf_counter() - t) * 1e6:.0f} μs")

    t = time.perf_counter()
    session.openService("//blp/refdata")
    logger.info(f"Open service: {(time.perf_counter() - t) * 1e6:.0f} μs")

    refdata = session.getService("//blp/refdata")

    iterations = 10
    logger.info(f"\nRunning {iterations} iterations...\n")

    logger.info(
        f"{'get_svc':>12} {'create_req':>12} {'append':>12} {'send_req':>12} {'wait_resp':>12} {'parse':>12} {'TOTAL':>12}"
    )
    logger.info("-" * 96)

    all_timings = []

    for i in range(iterations):
        timings = {}
        total_start = time.perf_counter()

        # Get service
        t = time.perf_counter()
        svc = session.getService("//blp/refdata")
        timings["get_svc"] = (time.perf_counter() - t) * 1e6

        # Create request
        t = time.perf_counter()
        req = svc.createRequest("ReferenceDataRequest")
        timings["create_req"] = (time.perf_counter() - t) * 1e6

        # Append securities and fields
        t = time.perf_counter()
        req.append("securities", "IBM US Equity")
        req.append("fields", "PX_LAST")
        timings["append"] = (time.perf_counter() - t) * 1e6

        # Send request
        t = time.perf_counter()
        session.sendRequest(req)
        timings["send_req"] = (time.perf_counter() - t) * 1e6

        # Wait for response
        t = time.perf_counter()
        while True:
            ev = session.nextEvent(5000)
            if ev.eventType() == blpapi.Event.RESPONSE:
                break
        timings["wait_resp"] = (time.perf_counter() - t) * 1e6

        # Parse response
        t = time.perf_counter()
        for msg in ev:
            security_data = msg.getElement("securityData")
            for sec in security_data.values():
                field_data = sec.getElement("fieldData")
                if field_data.hasElement("PX_LAST"):
                    _ = field_data.getElementAsFloat("PX_LAST")
        timings["parse"] = (time.perf_counter() - t) * 1e6

        timings["total"] = (time.perf_counter() - total_start) * 1e6

        logger.info(
            f"{timings['get_svc']:>12.0f} {timings['create_req']:>12.0f} {timings['append']:>12.0f} "
            f"{timings['send_req']:>12.0f} {timings['wait_resp']:>12.0f} {timings['parse']:>12.0f} {timings['total']:>12.0f}"
        )

        all_timings.append(timings)

    # Print averages
    logger.info("-" * 96)
    avg = {k: sum(t[k] for t in all_timings) / len(all_timings) for k in all_timings[0]}
    logger.info(
        f"{'AVG:':>4} {avg['get_svc']:>8.0f} {avg['create_req']:>12.0f} {avg['append']:>12.0f} "
        f"{avg['send_req']:>12.0f} {avg['wait_resp']:>12.0f} {avg['parse']:>12.0f} {avg['total']:>12.0f}"
    )

    logger.info("\nPhase breakdown (% of total):")
    logger.info(f"  get_service:     {avg['get_svc'] / avg['total'] * 100:>6.2f}%  ({avg['get_svc']:>8.0f} μs)")
    logger.info(f"  create_request:  {avg['create_req'] / avg['total'] * 100:>6.2f}%  ({avg['create_req']:>8.0f} μs)")
    logger.info(f"  append:          {avg['append'] / avg['total'] * 100:>6.2f}%  ({avg['append']:>8.0f} μs)")
    logger.info(f"  send_request:    {avg['send_req'] / avg['total'] * 100:>6.2f}%  ({avg['send_req']:>8.0f} μs)")
    logger.info(
        f"  wait_response:   {avg['wait_resp'] / avg['total'] * 100:>6.2f}%  ({avg['wait_resp']:>8.0f} μs)  <-- NETWORK + BLOOMBERG"
    )
    logger.info(f"  parse_response:  {avg['parse'] / avg['total'] * 100:>6.2f}%  ({avg['parse']:>8.0f} μs)")

    session.stop()
    logger.info("\n" + "=" * 40)
    logger.info("Complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
