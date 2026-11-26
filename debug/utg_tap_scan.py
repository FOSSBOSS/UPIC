#!/usr/bin/env python3
"""Listen for frequency-write clicks on either channel of a UNI-T UTG932E."""
import argparse
import csv
import os
import select
import sys
from pathlib import Path
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


def listen(device, vibrato, carriers, log, channel=1, retune_seconds=4):
    def write(command):
        device.write(f":CHANnel{channel}:" + command)

    def pitch(hz):
        write(f"BASE:FREQuency {hz:.6f}")

    def enter_within(seconds):
        if not sys.stdin.isatty():
            time.sleep(seconds)
            return False
        ready, _, _ = select.select([sys.stdin], [], [], seconds)
        return bool(ready and b"\n" in os.read(sys.stdin.fileno(), 4096))

    def trial(hz):
        print(f"{hz:g} Hz", flush=True)
        pitch(hz)
        if enter_within(1.5):
            return "settling"
        for i in range(2 * retune_seconds):
            start = time.monotonic()
            pitch(hz + 0.1 if i % 2 == 0 else hz)
            if enter_within(max(0, start + 0.5 - time.monotonic())):
                return "retuning"
        if enter_within(2):
            return "holding"
        return None

    try:
        write("OUTPut OFF")
        for cmd in ("MODe CONTINUE", "BASE:WAVe SINe", "AMPLitude:UNIT VPP",
                    "BASE:AMPLitude 0.1", "BASE:OFFSet 0"):
            write(cmd)
        pitch(carriers[0])
        if vibrato:
            for cmd in ("MODe FM", "MODulate:WAVe SINe", "MODulate:FREQuency 5",
                        "FM:FREQuency:DEV 4"):
                write(cmd)
        write("OUTPut ON")
        writer = csv.writer(log)
        mode = "FM" if vibrato else "pure"
        print("Press Enter when you hear tapping.", flush=True)
        for hz in carriers:
            started = time.monotonic()
            phase = trial(hz)
            elapsed = time.monotonic() - started
            if phase:
                print(f"Tapping {hz:g}  (CH{channel}, {elapsed:.2f} s, {phase})", flush=True)
            writer.writerow([mode, hz, 0.1, 500, phase or "unmarked", channel, retune_seconds,
                             f"{elapsed:.2f}" if phase else ""])
            log.flush()
    finally:
        write("OUTPut OFF")


#def arrow_keys():
    

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pure", action="store_true", help="use a plain sine instead of vibrato")
    parser.add_argument("--resource", help="explicit USB VISA resource")
    parser.add_argument("carriers", nargs="*", type=float, metavar="HZ",
                        help="carrier frequencies in Hz, in listening order")
    parser.add_argument("--channel", type=int, choices=(1, 2), default=1)
    parser.add_argument("--retune-seconds", type=int, default=4)
    args = parser.parse_args()
    if args.retune_seconds < 1:
        parser.error("--retune-seconds must be positive")
    carriers = args.carriers or [570, 110, 155.6, 220, 311.1, 440, 622.3, 880, 1244.5, 1760]
    if any(not 20 <= hz <= 20000 for hz in carriers):
        parser.error("choose carrier frequencies between 20 and 20000 Hz")
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
            path = Path("utg_tap_timing.csv").resolve()
            print(f"Logging to {path}")
            with path.open("a", newline="") as log:
                if log.tell() == 0:
                    csv.writer(log).writerow(["mode", "carrier_hz", "step_hz", "interval_ms", "heard",
                                              "channel", "retune_seconds", "mark_seconds_from_start"])
                listen(device, not args.pure, carriers, log, args.channel, args.retune_seconds)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
