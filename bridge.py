#!/usr/bin/env python3
"""Serve Sketch Score in a browser, with optional UNI-T UTG932E output."""
import argparse
from contextlib import ExitStack
import importlib
import importlib.util
import json
import math
import secrets
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import webbrowser

ROOT = Path(__file__).resolve().parent
PORT = 8765
ORIGIN = f"http://127.0.0.1:{PORT}"
LEASE = 1.5
REST_HZ = 0.01
VENDOR_ID = 0x6656
PRODUCT_ID = 0x0834


def installed(module):
    """Check optional packages without making them startup dependencies."""
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def detect_device():
    """Best-effort USB hint; PyVISA connection is the final authority."""
    try:
        import usb.core
        return usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID) is not None
    except Exception:
        # Missing PyUSB, missing USB backend, permissions, etc.
        return None


def connect_generator(args, resources):
    """Try the instrument and report availability; never abort browser startup."""
    importlib.invalidate_caches()
    libraries = {
        "pyvisa": installed("pyvisa"),
        "pyvisa_py": installed("pyvisa_py"),
        "pyusb": installed("usb.core"),
    }
    usb_found = detect_device() if libraries["pyusb"] else None
    info = {
        "browser_audio": True,
        "function_generator": False,
        "default_audio": "browser",
        "libraries": libraries,
        "usb_detected": usb_found,
        "identity": None,
        "reason": None,
    }

    def unavailable(reason):
        info["reason"] = reason
        return None, info

    if not libraries["pyvisa"]:
        return unavailable("PyVISA not installed (pip install pyvisa).")
    if args.backend == "@py" and not libraries["pyvisa_py"]:
        return unavailable("PyVISA-py backend missing (pip install pyvisa-py).")
    if args.backend == "@py" and not libraries["pyusb"]:
        return unavailable("PyUSB missing (pip install pyusb).")

    try:
        import pyvisa
        manager = pyvisa.ResourceManager(args.backend)
        resources.callback(manager.close)

        matches = []
        for resource in manager.list_resources():
            parts = resource.split("::")
            if not parts[0].startswith("USB") or len(parts) < 4:
                continue
            try:
                ids = int(parts[1], 0), int(parts[2], 0)
            except ValueError:
                continue
            if ids == (VENDOR_ID, PRODUCT_ID):
                matches.append(resource)

        if args.resource:
            resource_name = args.resource
        elif len(matches) == 1:
            resource_name = matches[0]
        elif not matches:
            return unavailable("UTG900E/UTG932E not detected. Check USB cable and permissions.")
        else:
            return unavailable(f"Multiple UNI-T generators found: {matches}. Use --resource.")

        device = manager.open_resource(resource_name)
        resources.callback(device.close)
        device.timeout = 1500
        device.write_termination = "\n"
        device.read_termination = None  # UTG900E replies without a final newline.
        identity = device.query("*IDN?").strip()
        fields = identity.split(",")
        if len(fields) < 2 or fields[1].strip().upper() not in {"UTG900E", "UTG932E"}:
            return unavailable("Unexpected instrument identity: " + identity)

        instrument = Instrument(device, args.trace)
        instrument.off()
        info.update(function_generator=True, default_audio="hardware", identity=identity)
        return instrument, info
    except Exception as exc:
        # Covers missing USB backend, VISA load errors, permissions, device read errors.
        return unavailable(f"Function generator not available: {exc}")


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
        path = urlsplit(self.path).path
        if path == "/capabilities":
            self.server.refresh_generator()
            return self.reply(200, self.server.capabilities)
        files = {"/": ("index.html", "text/html"), "/score.js": ("score.js", "text/javascript"),
                 "/hardware.js": ("hardware.js", "text/javascript")}
        if path in files:
            name, mime = files[path]
            try:
                return self.reply(200, (ROOT / name).read_bytes(), mime)
            except FileNotFoundError:
                return self.reply(404, {"error": f"Missing {name}"})
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
                server.refresh_generator()
                if server.instrument is None:
                    return self.reply(503, {"error": server.capabilities["reason"] or "Function generator unavailable."})
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
                            type(note[1]) in (int, float) and (note[1] == REST_HZ or 110 <= note[1] <= 2600)):
                        raise ValueError("Invalid voice")
                server.instrument.frame(notes)
                server.deadline = time.monotonic() + LEASE
            else:
                return self.reply(404, {})
            self.reply(200, {})
        except Exception as exc:
            server.release(f"{self.path} failed: {exc}", invalidate=True)
            self.reply(400, {"error": str(exc)})


class Bridge(HTTPServer):
    owner = None
    deadline = 0

    def close_resources(self):
        # ExitStack attempts every registered close, even if one fails.
        try:
            self.resources.close()
        except Exception as exc:
            print(f"[UPIC] VISA cleanup: {exc}", file=sys.stderr)

    def invalidate_generator(self, reason):
        self.owner = None
        self.deadline = 0
        self.instrument = None
        self.capabilities.update(
            function_generator=False, default_audio="browser",
            identity=None, usb_detected=None, reason=reason)
        self.close_resources()

    def refresh_generator(self):
        if self.owner:
            return
        if self.instrument is not None:
            try:
                identity = self.instrument.device.query("*IDN?").strip()
                if identity == self.capabilities["identity"]:
                    return
            except Exception:
                pass
            self.release("instrument disconnected", invalidate=True)
        self.close_resources()
        self.instrument, self.capabilities = connect_generator(
            self.args, self.resources)
        if self.instrument is None:
            self.close_resources()

    def release(self, reason, invalidate=False):
        self.owner = None
        self.deadline = 0
        if self.instrument is not None:
            if self.instrument.trace:
                print(f"Releasing both outputs: {reason}", flush=True)
            try:
                self.instrument.off()
            except Exception as exc:
                print(exc, file=sys.stderr)
                reason = str(exc)
                invalidate = True
        if invalidate:
            self.invalidate_generator(reason)

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

    # Keep the web UI available whether or not instrument probing succeeds.
    with ExitStack() as resources:
        instrument, capabilities = connect_generator(args, resources)
        with Bridge(("127.0.0.1", PORT), Handler) as server:
            server.args = args
            server.resources = resources
            server.instrument = instrument
            server.capabilities = capabilities
            if instrument is None:
                try:
                    resources.close()
                except Exception as exc:
                    print(f"[UPIC] VISA cleanup: {exc}", file=sys.stderr)
            server.timeout = .1

            if instrument is None:
                print(f"[UPIC] {capabilities['reason']}", flush=True)
                print("[UPIC] Default: Browser Audio", flush=True)
            else:
                print(f"[UPIC] {capabilities['identity']}", flush=True)
                print("[UPIC] Default: Function Generator", flush=True)
            print(f"[UPIC] Opening {ORIGIN}  (Ctrl-C to quit)", flush=True)
            if not webbrowser.open(ORIGIN):
                print(f"[UPIC] Open {ORIGIN} manually.", flush=True)

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
