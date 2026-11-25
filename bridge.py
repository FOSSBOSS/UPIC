#!/usr/bin/env python3
"""Run in the PyVISA environment that already talks to your UNI-T UTG932E."""
import argparse
from contextlib import closing
import json
import math
import secrets
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pyvisa

ROOT = Path(__file__).resolve().parent
PORT = 8765
ORIGIN = f"http://127.0.0.1:{PORT}"
LEASE = 1.5
REST_HZ = 0.01


class Instrument:
    def __init__(self, device, trace=False):
        self.trace = trace
        self.boundary = False
        self.device = device
        self.state = [None, None]

    def command(self, channel, command):
        message = f":CHANnel{channel}:{command}"
        if self.trace and (self.boundary or command.startswith("OUTPut")):
            print("  >", message, flush=True)
        self.device.write(message)

    def snapshot(self, channel, when):
        fields = []
        for key in ("OUTPut", "BASE:FREQuency", "MODe"):
            try:
                value = self.device.query(f":CHANnel{channel}:{key}?").strip()
            except Exception as exc:
                print(f"  {when} CH{channel} {key}? failed: {exc}", flush=True)
                return
            fields.append(f"{key}={value}")
        print(f"  {when} CH{channel} " + " ".join(fields), flush=True)

    def off(self):
        errors = []
        for channel in (1, 2):
            try:
                self.command(channel, "OUTPut OFF")
            except Exception as exc:
                errors.append(str(exc))
        self.state = [None, None]
        if errors:
            raise RuntimeError("Could not confirm outputs off: " + ", ".join(errors))

    def configure(self):
        self.off()
        for ch in (1, 2):
            for cmd in ("MODe CONTINUE", "BASE:WAVe SINe", "AMPLitude:UNIT VPP",
                        "BASE:AMPLitude 0.1", "BASE:OFFSet 0", f"BASE:FREQuency {REST_HZ}"):
                self.command(ch, cmd)
            for key, expected in (("BASE:AMPLitude", 0.1), ("BASE:OFFSet", 0)):
                value = float(self.device.query(f":CHANnel{ch}:{key}?"))
                if not math.isclose(value, expected, abs_tol=0.001):
                    raise ValueError(f"CH{ch} {key} read back {value}")

        for ch in (1, 2):
            self.command(ch, "OUTPut ON")

    def frame(self, notes):
        modes = ("CONTINUE", "AM", "FM", "FM")
        for idx, note in enumerate(notes):
            ch = idx + 1
            old_ink, old_hz = self.state[idx] or (0, REST_HZ)
            # A rest retains the active brush and its hardware modulation mode.
            resting = note is None or note[1] == REST_HZ
            ink, hz = (old_ink, REST_HZ) if resting else note
            if (ink, hz) == (old_ink, old_hz):
                continue

            self.boundary = self.trace and (old_hz == REST_HZ or hz == REST_HZ)
            if self.boundary:
                print(f"CH{ch} {'enter rest' if resting else 'leave rest'}", flush=True)
                self.snapshot(ch, "before")
            old_mode, mode = modes[old_ink], modes[ink]
            if mode == "FM":
                deviation = 0 if resting else (4 if ink == 2 else min(180, hz))
                previous = 0 if old_hz == REST_HZ else (4 if old_ink == 2 else min(180, old_hz))
                # Reduce deviation first so the lower carrier is valid.
                if old_mode == "FM" and deviation < previous:
                    self.command(ch, f"FM:FREQuency:DEV {deviation}")
            if old_mode == "FM" and mode != "FM":
                self.command(ch, f"MODe {mode}")
            if hz != old_hz:
                self.command(ch, f"BASE:FREQuency {hz}")
            if old_mode != mode and old_mode != "FM":
                self.command(ch, f"MODe {mode}")
            if ink != old_ink and ink:
                if mode != old_mode:
                    self.command(ch, "MODulate:WAVe SINe")
                self.command(ch, f"MODulate:FREQuency {110 if ink == 3 else 5}")
                if mode == "AM":
                    self.command(ch, "MODulate:DEPTh 70")
            if mode == "FM" and (old_mode != "FM" or deviation > previous):
                self.command(ch, f"FM:FREQuency:DEV {deviation}")
            self.state[idx] = (ink, hz)
            if self.boundary:
                self.snapshot(ch, "after")
                self.boundary = False



class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, data, content="application/json"):
        body = data if isinstance(data, bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", content)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        try:
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # A dropped reply does not end playback; the heartbeat handles a lost client.
            pass

    def do_GET(self):
        files = {"/": ("index.html", "text/html"), "/score.js": ("score.js", "text/javascript"),
                 "/hardware.js": ("hardware.js", "text/javascript")}
        if self.path in files:
            name, mime = files[self.path]
            self.reply(200, (ROOT / name).read_bytes(), mime)
        else:
            self.reply(404, {})

    def do_POST(self):
        server = self.server
        if self.headers.get("Origin") != ORIGIN or self.headers.get("Host") != ORIGIN[7:]:
            return self.reply(403, {"error": "Open the local Sketch Score URL."})
        try:
            size = int(self.headers.get("Content-Length", 0))
            if not 0 < size <= 1024:
                raise ValueError("Invalid request size")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError("Invalid request")
            if self.path == "/start":
                if server.owner:
                    return self.reply(409, {"error": "Another tab is playing."})
                server.instrument.configure()
                server.owner = secrets.token_urlsafe(24)
                server.deadline = time.monotonic() + LEASE
                return self.reply(200, {"token": server.owner})
            if not server.owner or data.get("token") != server.owner:
                return self.reply(409, {"error": "Playback ended. Press Play again."})
            if self.path == "/stop":
                if server.instrument.trace:
                    print("Browser requested /stop", flush=True)
                server.instrument.off()
                server.owner = None
            elif self.path == "/frame":
                notes = data.get("notes")
                if not isinstance(notes, list) or len(notes) != 2:
                    raise ValueError("Expected two channels")
                for note in notes:
                    if note is None:
                        continue
                    if not (isinstance(note, list) and len(note) == 2 and
                            type(note[0]) is int and 0 <= note[0] <= 3 and
                            type(note[1]) in (int, float) and (note[1] == REST_HZ or 110 <= note[1] <= 1760)):
                        raise ValueError("Invalid voice")
                server.instrument.frame(notes)
                server.deadline = time.monotonic() + LEASE
            else:
                return self.reply(404, {})
            self.reply(200, {})
        except Exception as exc:
            server.release(f"{self.path} failed: {exc}")
            self.reply(400, {"error": str(exc)})


class Bridge(HTTPServer):
    owner = None
    deadline = 0

    def release(self, reason):
        if self.instrument.trace:
            print(f"Releasing both outputs: {reason}", flush=True)
        self.owner = None
        try:
            self.instrument.off()
        except Exception as exc:
            print(exc, file=sys.stderr)

    def get_request(self):
        conn, peer = super().get_request()
        conn.settimeout(.5)
        return conn, peer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resource", help="Explicit VISA resource")
    parser.add_argument("--backend", default="@py", help="PyVISA backend (default @py)")
    parser.add_argument("--trace", action="store_true", help="Show output state and SCPI at rest boundaries")
    args = parser.parse_args()
    with closing(pyvisa.ResourceManager(args.backend)) as manager:
        choices = [r for r in manager.list_resources() if r.startswith("USB") and
                   len(r.split("::")) >= 4 and
                   [int(v, 0) for v in r.split("::")[1:3]] == [0x6656, 0x0834]]
        if not args.resource and len(choices) != 1:
            sys.exit(f"Expected one UTG900E. Matches: {choices}. Use --resource if needed.")
        with closing(manager.open_resource(args.resource or choices[0])) as device:
            device.timeout = 1500
            device.write_termination = device.read_termination = "\n"
            device.read_termination = None # pyvisa bug not yet filed
            identity = device.query("*IDN?").strip()
            if len(identity.split(",")) < 2 or identity.split(",")[1].strip().upper() not in {"UTG900E","UTG932E"}:
                sys.exit("Unexpected instrument: " + identity)
            with Bridge(("127.0.0.1", PORT), Handler) as server:
                server.instrument = Instrument(device, args.trace)
                server.timeout = .1
                print(f"{identity}\nOpen {ORIGIN} in your browser. Ctrl-C to quit.", flush=True)
                try:
                    while True:
                        if server.owner and time.monotonic() >= server.deadline:
                            server.release("browser heartbeat expired")
                        server.handle_request()
                except KeyboardInterrupt:
                    pass
                finally:
                    if server.owner:
                        server.release("bridge shutdown")


if __name__ == "__main__":
    main()
