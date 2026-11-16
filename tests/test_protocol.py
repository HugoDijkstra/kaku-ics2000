"""Compare our frame builder and crypto against ics-2000-python.

Run: uv run --with ics-2000-python --with cryptography --with aiohttp pytest tests -q
"""

import importlib.util
import json
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "kaku_ics2000"

# Load api.py without Home Assistant installed.
pkg = types.ModuleType("kaku_ics2000")
pkg.__path__ = [str(ROOT)]
sys.modules["kaku_ics2000"] = pkg
for name in ("const", "api"):
    spec = importlib.util.spec_from_file_location(f"kaku_ics2000.{name}", ROOT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"kaku_ics2000.{name}"] = mod
    spec.loader.exec_module(mod)
api = sys.modules["kaku_ics2000.api"]

from ics_2000.command import Command  # noqa: E402
from ics_2000.encryption import decrypt as ref_decrypt, encrypt as ref_encrypt  # noqa: E402
from ics_2000.model.entity_type import Entity_Type  # noqa: E402

KEY = "00112233445566778899aabbccddeeff"
MAC = "0012a302aba4"


def test_encrypt_matches_reference():
    for text in ("", "a", json.dumps({"module": {"id": 7, "function": 0, "value": 1}}), "x" * 33):
        assert api.encrypt(text, KEY) == bytes(ref_encrypt(text, KEY))


def test_decrypt_roundtrip_with_reference():
    import base64
    blob = base64.b64encode(bytes(ref_encrypt('{"hello": 1}', KEY))).decode()
    assert api.decrypt(blob, KEY) == ref_decrypt(blob, KEY) == '{"hello": 1}'


def test_command_frame_matches_reference():
    for device_id, func, value in ((1, 0, 1), (42, 1, 15), (123456, 4, 200), (9, 3, 0)):
        ours = api.build_command(MAC, KEY, device_id, func, value)
        ref = Command(MAC, device_id, func, value, KEY, Entity_Type.Module).total_message
        assert ours == ref, (device_id, func, value)


def test_normalize_mac():
    assert api.normalize_mac("00:12:A3:02:AB:A4") == MAC
