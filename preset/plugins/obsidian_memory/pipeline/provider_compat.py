#!/usr/bin/env python3
"""Compatibility helpers for Hermes provider config.

Hermes moved custom endpoints from the legacy ``custom_providers:`` list to the
``providers:`` map (config v12).  These helpers let the scheduled scripts read
and write either shape, so they keep working after the migration without
reintroducing the retired list.
"""
from __future__ import annotations

import datetime
import os
import shutil
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

import yaml


def load_config(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8-sig") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def save_config(cfg: Dict[str, Any], path: str, tag: str = "provider-compat") -> str:
    """Back up and write *cfg*.  Returns the backup path."""
    stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    bak = f"{path}.bak-{tag}-{stamp}"
    shutil.copy2(path, bak)
    try:
        mode = os.stat(path).st_mode & 0o777
    except OSError:
        mode = 0o600
    tmp = f"{path}.tmp-{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        os.chmod(tmp, mode)
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    os.replace(tmp, path)
    return bak


def provider_entries(cfg: Dict[str, Any]) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """Yield ``(key, entry)`` for the ``providers:`` map first, then the legacy list."""
    providers = cfg.get("providers")
    if isinstance(providers, dict):
        for key, entry in providers.items():
            if isinstance(entry, dict):
                yield str(key), entry
    legacy = cfg.get("custom_providers")
    if isinstance(legacy, list):
        for entry in legacy:
            if isinstance(entry, dict):
                yield str(entry.get("name") or ""), entry


def find_provider(cfg: Dict[str, Any], name: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """Find a provider by map key or display name (case-insensitive)."""
    wanted = str(name or "").strip().lower()
    if not wanted:
        return None, None
    for key, entry in provider_entries(cfg):
        if key.strip().lower() == wanted or str(entry.get("name") or "").strip().lower() == wanted:
            return key, entry
    return None, None


def provider_url(entry: Dict[str, Any]) -> str:
    return str(entry.get("api") or entry.get("base_url") or entry.get("url") or "").rstrip("/")


def model_map(entry: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Return ``{model_id: metadata}`` for list- or map-shaped ``models``."""
    models = entry.get("models")
    out: Dict[str, Dict[str, Any]] = {}
    if isinstance(models, dict):
        for mid, meta in models.items():
            if mid:
                out[str(mid)] = dict(meta) if isinstance(meta, dict) else {}
    elif isinstance(models, list):
        for item in models:
            if isinstance(item, dict):
                mid = item.get("id") or item.get("name")
                if mid:
                    out[str(mid)] = {k: v for k, v in item.items() if k != "id"}
            elif isinstance(item, str):
                out[item] = {}
    return out


def model_ids(entry: Dict[str, Any]) -> List[str]:
    return list(model_map(entry).keys())


def set_models(entry: Dict[str, Any], ids: Iterable[str]) -> None:
    """Set ``models`` in the v12 map shape, preserving metadata for kept ids."""
    old = model_map(entry)
    entry["models"] = {str(mid): dict(old.get(str(mid)) or {}) for mid in ids}


def api_key(entry: Dict[str, Any], env: Optional[Dict[str, str]] = None) -> str:
    key = entry.get("api_key")
    if isinstance(key, str) and key.strip():
        return key.strip()
    key_env = entry.get("key_env") or entry.get("api_key_env")
    if key_env:
        if env and key_env in env:
            return str(env[key_env]).strip()
        return str(os.environ.get(str(key_env), "")).strip()
    return ""


def provider_key(cfg: Dict[str, Any], name: str) -> Optional[str]:
    return find_provider(cfg, name)[0]