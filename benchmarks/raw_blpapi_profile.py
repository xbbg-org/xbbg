"""Raw blpapi profiled benchmark - compare with Rust."""

import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
import blpapi


def main():
    print("Raw blpapi Profiled BDP Benchmark")
    print("=" * 40)

    # Setup session
    options = blpapi.SessionOptions()
    options.setServerHost("127.0.0.1")
    options.setServerPort(8194)

    session = blpapi.Session(options)

    t = time.perf_counter()
    session.start()
    print(f"Session start: {(time.perf_counter() - t) * 1e6:.0f} μs")

    t = time.perf_counter()
    session.openService("//blp/refdata")
    print(f"Open service: {(time.perf_counter() - t) * 1e6:.0f} μs")

    refdata = session.getService("//blp/refdata")

    iterations = 10
    print(f"\nRunning {iterations} iterations...\n")

    print(
        f"{'get_svc':>12} {'create_req':>12} {'append':>12} {'send_req':>12} {'wait_resp':>12} {'parse':>12} {'TOTAL':>12}"
    )
    print("-" * 96)

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

        print(
            f"{timings['get_svc']:>12.0f} {timings['create_req']:>12.0f} {timings['append']:>12.0f} "
            f"{timings['send_req']:>12.0f} {timings['wait_resp']:>12.0f} {timings['parse']:>12.0f} {timings['total']:>12.0f}"
        )

        all_timings.append(timings)

    # Print averages
    print("-" * 96)
    avg = {k: sum(t[k] for t in all_timings) / len(all_timings) for k in all_timings[0]}
    print(
        f"{'AVG:':>4} {avg['get_svc']:>8.0f} {avg['create_req']:>12.0f} {avg['append']:>12.0f} "
        f"{avg['send_req']:>12.0f} {avg['wait_resp']:>12.0f} {avg['parse']:>12.0f} {avg['total']:>12.0f}"
    )

    print(f"\nPhase breakdown (% of total):")
    print(f"  get_service:     {avg['get_svc'] / avg['total'] * 100:>6.2f}%  ({avg['get_svc']:>8.0f} μs)")
    print(f"  create_request:  {avg['create_req'] / avg['total'] * 100:>6.2f}%  ({avg['create_req']:>8.0f} μs)")
    print(f"  append:          {avg['append'] / avg['total'] * 100:>6.2f}%  ({avg['append']:>8.0f} μs)")
    print(f"  send_request:    {avg['send_req'] / avg['total'] * 100:>6.2f}%  ({avg['send_req']:>8.0f} μs)")
    print(
        f"  wait_response:   {avg['wait_resp'] / avg['total'] * 100:>6.2f}%  ({avg['wait_resp']:>8.0f} μs)  <-- NETWORK + BLOOMBERG"
    )
    print(f"  parse_response:  {avg['parse'] / avg['total'] * 100:>6.2f}%  ({avg['parse']:>8.0f} μs)")

    session.stop()
    print("\n" + "=" * 40)
    print("Complete.")


if __name__ == "__main__":
    main()
