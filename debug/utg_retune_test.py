#!/usr/bin/env python3
"""Listen for frequency-write clicks on CH1 of a UNI-T UTG932E."""
import argparse
from contextlib import closing
import time


def usb_match(resource):
    fields = resource.split("::")
    if not resource.startswith("USB") or len(fields) < 4:
        return False
    try:
        return [int(v, 0) for v in fields[1:3]] == [0x6656, 0x0834]
    except ValueError:
        return False


def listen(device, vibrato, step, interval):
    def write(command):
        device.write(":CHANnel1:" + command)

    def pitch(hz):
        write(f"BASE:FREQuency {hz:.6f}")

    def hold(label):
        print(label, flush=True)
        time.sleep(4)

    def timed_writes(alternate):
        start = time.monotonic()
        for i in range(40):
            sent = time.monotonic()
            pitch(570 + step if alternate and i % 2 == 0 else 570)
            time.sleep(max(0, sent + interval - time.monotonic()))
        print(f"  Average interval including USB writes: {(time.monotonic()-start)*25:.1f} ms")

    try:
        write("OUTPut OFF")
        for cmd in ("MODe CONTINUE", "BASE:WAVe SINe", "AMPLitude:UNIT VPP",
                    "BASE:AMPLitude 0.1", "BASE:OFFSet 0"):
            write(cmd)
        pitch(570)
        if vibrato:
            for cmd in ("MODe FM", "MODulate:WAVe SINe", "MODulate:FREQuency 5",
                        "FM:FREQuency:DEV 4"):
                write(cmd)
        write("OUTPut ON")
        hold("A  Hold 570 Hz")
        print("B  Repeatedly write 570 Hz", flush=True)
        timed_writes(False)
        hold("C  Hold 570 Hz")
        print(f"D  Alternate 570 and {570+step:g} Hz", flush=True)
        timed_writes(True)
        hold("E  Hold 570 Hz")
    finally:
        write("OUTPut OFF")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pure", action="store_true", help="use a plain sine instead of vibrato")
    parser.add_argument("--resource", help="explicit USB VISA resource")
    parser.add_argument("--step-hz", type=float, default=0.1)
    parser.add_argument("--interval-ms", type=float, default=86)
    args = parser.parse_args()
    if not 0.000001 <= args.step_hz <= 100 or not 1 <= args.interval_ms <= 2000:
        parser.error("use a step of 0.000001–100 Hz and an interval of 1–2000 ms")

    import pyvisa
    with closing(pyvisa.ResourceManager("@py")) as manager:
        resource = args.resource
        if not resource:
            matches = [r for r in manager.list_resources() if usb_match(r)]
            if len(matches) != 1:
                parser.exit(1, f"Expected one UTG. Found {matches}. Use --resource.\n")
            resource = matches[0]
        with closing(manager.open_resource(resource)) as device:
            device.timeout = 2000
            device.read_termination = None
            device.write_termination = "\n"
            identity = device.query("*IDN?").strip()
            if identity.split(",")[1:2] not in (["UTG900E"], ["UTG932E"]):
                parser.exit(1, f"Unexpected instrument: {identity}\n")
            print(identity, " | ", "Pure sine" if args.pure else "5 Hz vibrato")
            listen(device, not args.pure, args.step_hz, args.interval_ms / 1000)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
