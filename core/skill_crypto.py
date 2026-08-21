#!/usr/bin/env python3
"""
Offline Ed25519 signing for SEEM gated skill packages.

No network I/O. Private keys stay on the signing host.
Canonical payload = JSON with manifest.signature cleared, sort_keys, compact separators.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

try:
    from nacl.exceptions import BadSignatureError
    from nacl.signing import SigningKey, VerifyKey
    from nacl.encoding import HexEncoder
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "PyNaCl is required for skill signing. Install with: pip install pynacl"
    ) from e


PLACEHOLDER_SIGNATURES = {
    "",
    "UNSIGNED_DEV_PLACEHOLDER",
    "unsigned",
    "NONE",
}


def canonical_package_bytes(package: Dict[str, Any]) -> bytes:
    """Deterministic bytes for signing/verification (signature field zeroed)."""
    body = deepcopy(package)
    if "manifest" not in body or not isinstance(body["manifest"], dict):
        raise ValueError("package.manifest missing")
    body["manifest"]["signature"] = ""
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def generate_keypair() -> tuple[str, str]:
    """
    Returns (signing_key_hex, verify_key_hex).
    signing_key_hex must remain offline/private.
    """
    sk = SigningKey.generate()
    vk = sk.verify_key
    return (
        sk.encode(encoder=HexEncoder).decode("ascii"),
        vk.encode(encoder=HexEncoder).decode("ascii"),
    )


def signing_key_from_hex(sk_hex: str) -> SigningKey:
    return SigningKey(sk_hex.encode("ascii"), encoder=HexEncoder)


def verify_key_from_hex(vk_hex: str) -> VerifyKey:
    return VerifyKey(vk_hex.encode("ascii"), encoder=HexEncoder)


def sign_package(package: Dict[str, Any], signing_key_hex: str) -> Dict[str, Any]:
    """Return a new package dict with manifest.signature set (hex)."""
    payload = canonical_package_bytes(package)
    sk = signing_key_from_hex(signing_key_hex)
    signed = sk.sign(payload)
    # nacl attaches signature prefix; store signature hex only
    sig_hex = signed.signature.hex()
    out = deepcopy(package)
    out["manifest"]["signature"] = sig_hex
    return out


def is_placeholder_signature(sig: Optional[str]) -> bool:
    if sig is None:
        return True
    return str(sig).strip() in PLACEHOLDER_SIGNATURES or str(sig).startswith("UNSIGNED")


def verify_package(
    package: Dict[str, Any],
    trusted_verify_keys_hex: Iterable[str],
) -> bool:
    """
    Verify manifest.signature against any trusted verify key.
    Raises ValueError/PermissionError on hard failures; returns True on success.
    """
    sig = package.get("manifest", {}).get("signature")
    if is_placeholder_signature(sig):
        raise PermissionError("skill package signature missing or placeholder")

    payload = canonical_package_bytes(package)
    sig_bytes = bytes.fromhex(str(sig))
    keys = list(trusted_verify_keys_hex)
    if not keys:
        raise PermissionError("no trusted verify keys configured")

    last_err: Optional[Exception] = None
    for vk_hex in keys:
        try:
            vk = verify_key_from_hex(vk_hex)
            vk.verify(payload, sig_bytes)
            return True
        except BadSignatureError as e:
            last_err = e
            continue
        except Exception as e:
            last_err = e
            continue
    raise PermissionError(f"skill package signature verification failed: {last_err}")


def save_keypair(
    directory: Union[str, Path],
    sk_hex: str,
    vk_hex: str,
    name: str = "skill_root",
) -> Dict[str, Path]:
    """Write key material locally. Caller must keep *.sk secret."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    sk_path = directory / f"{name}.sk"
    vk_path = directory / f"{name}.pub"
    sk_path.write_text(sk_hex + "\n", encoding="utf-8")
    vk_path.write_text(vk_hex + "\n", encoding="utf-8")
    try:
        sk_path.chmod(0o600)
    except OSError:
        pass
    return {"signing_key": sk_path, "verify_key": vk_path}


def load_verify_keys(paths: Iterable[Union[str, Path]]) -> List[str]:
    keys: List[str] = []
    for p in paths:
        text = Path(p).read_text(encoding="utf-8").strip()
        if text:
            keys.append(text.split()[0])
    return keys
