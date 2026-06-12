#!/usr/bin/env python3
"""Record full RPC request/response fixtures from chain templates.

The recorder uses the same chain_adapters code path as target_generator.sh, so
captured fixtures describe the exact requests that Vegeta will send.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
CHAINS_DIR = REPO / "config" / "chains"
DEFAULT_OUTPUT_DIR = REPO / "docs" / "audit" / "rpc-fixtures"
DEFAULT_FIXTURES_DIR = REPO / "tools" / "fake-node" / "fixtures"
FAKE_NODE_CONFIGS_DIR = REPO / "tools" / "fake-node" / "configs"

sys.path.insert(0, str(REPO / "tools"))
from chain_adapters import get_adapter  # noqa: E402

ENV_DEFAULT_RE = re.compile(r"^\$\{([A-Z][A-Z0-9_]*):-([^}]*)\}$")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def safe_name(value: str) -> str:
    value = value.replace("/", "_")
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "method"


def load_fixture_map(family: str) -> dict[str, str]:
    path = FAKE_NODE_CONFIGS_DIR / f"{family}.yaml"
    if not path.exists():
        return {}
    mapping: dict[str, str] = {}
    in_methods = False
    current: str | None = None
    for line in path.read_text().splitlines():
        raw = line.split("#", 1)[0].rstrip()
        if not raw.strip():
            continue
        if raw.strip() == "methods:":
            in_methods = True
            current = None
            continue
        if in_methods and not raw.startswith(" "):
            break
        if not in_methods:
            continue
        method_match = re.match(r"^  ([^:\n]+):\s*$", raw)
        if method_match:
            current = method_match.group(1).strip().strip("'\"")
            continue
        fixture_match = re.match(r"^\s+fixture:\s*(.+?)\s*$", raw)
        if fixture_match and current:
            mapping[current] = fixture_match.group(1).strip().strip("'\"")
    return mapping


def split_methods(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value or "").split(",") if v.strip()]


def chain_names(selected: str) -> list[str]:
    if selected == "all":
        return sorted(p.stem for p in CHAINS_DIR.glob("*.json"))
    return [c.strip() for c in selected.split(",") if c.strip()]


def configured_methods(tpl: dict[str, Any], modes: set[str]) -> list[dict[str, Any]]:
    rpc_methods = tpl.get("rpc_methods", {})
    by_method: dict[str, dict[str, Any]] = {}

    if "single" in modes:
        method = str(rpc_methods.get("single", "")).strip()
        if method:
            by_method.setdefault(method, {"method": method, "modes": [], "weight": 1})
            by_method[method]["modes"].append("single")

    if "mixed" in modes:
        weighted = rpc_methods.get("mixed_weighted") or []
        if isinstance(weighted, list) and weighted:
            for item in weighted:
                if not isinstance(item, dict):
                    continue
                method = str(item.get("method", "")).strip()
                if not method:
                    continue
                entry = by_method.setdefault(method, {"method": method, "modes": [], "weight": 0})
                entry["modes"].append("mixed")
                try:
                    entry["weight"] = max(entry.get("weight", 0), int(item.get("weight", 1)))
                except (TypeError, ValueError):
                    entry["weight"] = max(entry.get("weight", 0), 1)
        else:
            for method in split_methods(rpc_methods.get("mixed", "")):
                entry = by_method.setdefault(method, {"method": method, "modes": [], "weight": 1})
                entry["modes"].append("mixed")

    return sorted(by_method.values(), key=lambda x: x["method"])


def choose_endpoint(tpl: dict[str, Any], override: str | None) -> str | None:
    if override:
        return override
    rpc_url = tpl.get("rpc_url")
    if rpc_url and rpc_url != "LOCAL_RPC_URL":
        return str(rpc_url)
    for endpoint in tpl.get("_meta", {}).get("original_public_endpoints", []):
        url = endpoint.get("url") if isinstance(endpoint, dict) else None
        if url:
            return str(url)
    return None


def choose_address(tpl: dict[str, Any], override: str | None) -> str:
    if override:
        return override
    params = tpl.get("params", {})
    if isinstance(params, dict) and params.get("target_address"):
        return str(resolve_template_value(params["target_address"]))
    addresses = tpl.get("system_addresses", [])
    if isinstance(addresses, list) and addresses:
        return str(addresses[0])
    return "0x0000000000000000000000000000000000000000"


def resolve_template_value(value: Any) -> Any:
    if isinstance(value, str):
        match = ENV_DEFAULT_RE.match(value)
        if match:
            env_name, fallback = match.groups()
            return os.environ.get(env_name) or fallback
        return os.environ.get(value, value)
    return value


def vegeta_to_request(target: dict[str, Any], param_format: str) -> dict[str, Any]:
    headers = {}
    for key, value in target.get("header", {}).items():
        if isinstance(value, list):
            headers[key] = value[0] if value else ""
        else:
            headers[key] = value
    body = ""
    if target.get("body"):
        body = base64.b64decode(target["body"]).decode("utf-8")
    return {
        "method": target["method"],
        "url": target["url"],
        "headers": headers,
        "body": body,
        "param_format": param_format,
        "vegeta_target": target,
    }


def build_request(chain: str, tpl: dict[str, Any], method: str, endpoint: str, address: str) -> dict[str, Any]:
    os.environ["BLOCKCHAIN_NODE"] = chain
    adapter = get_adapter(chain)
    param_format = tpl.get("param_formats", {}).get(method, "single_address")
    target = adapter.build_vegeta_target(method, address, endpoint, str(param_format))
    return vegeta_to_request(target, str(param_format))


def build_health_request(chain: str, endpoint: str) -> tuple[str, dict[str, Any]]:
    os.environ["BLOCKCHAIN_NODE"] = chain
    adapter = get_adapter(chain)
    probe = adapter.health_check_request(endpoint)
    body = probe.get("body") or ""
    method_name = ""
    try:
        parsed = json.loads(body) if body else {}
        if isinstance(parsed, dict):
            method_name = str(parsed.get("method") or "")
    except json.JSONDecodeError:
        method_name = ""
    if not method_name:
        url = str(probe.get("url") or "")
        method_name = f"{probe.get('method', 'GET')} {url.split(endpoint.rstrip('/'), 1)[-1] or '/'}"
    return method_name, {
        "method": probe.get("method", "GET"),
        "url": probe["url"],
        "headers": probe.get("headers", {}),
        "body": body,
        "param_format": "health_probe",
        "parse_jq": probe.get("parse_jq"),
        "vegeta_target": None,
    }


def send_request(request_data: dict[str, Any], timeout: float) -> dict[str, Any]:
    body = request_data["body"].encode("utf-8") if request_data["body"] else None
    headers = request_data.get("headers", {})
    # Add a User-Agent to avoid basic Cloudflare blocks.
    if "User-Agent" not in headers:
        headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    req = urllib.request.Request(
        request_data["url"],
        data=body,
        headers=headers,
        method=request_data["method"],
    )
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body_bytes = resp.read()
            text = body_bytes.decode("utf-8", errors="replace")
            parsed = None
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                pass
            return {
                "ok": 200 <= resp.status < 400 and is_semantic_success(parsed, text),
                "http_status": resp.status,
                "headers": dict(resp.headers.items()),
                "body_text": text,
                "json": parsed,
                "elapsed_ms": round((time.time() - started) * 1000, 3),
            }
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return {
            "ok": False,
            "http_status": exc.code,
            "headers": dict(exc.headers.items()),
            "body_text": text,
            "json": try_json(text),
            "elapsed_ms": round((time.time() - started) * 1000, 3),
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "http_status": None,
            "headers": {},
            "body_text": "",
            "json": None,
            "elapsed_ms": round((time.time() - started) * 1000, 3),
            "error": str(exc),
        }


def try_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


PLACEHOLDER_MARKERS = ("needs_real_recording", "placeholder", "\u5360\u4f4d")


def is_semantic_success(parsed: Any, text: str) -> bool:
    if isinstance(parsed, dict):
        if parsed.get("error") is not None:
            return False
        if parsed.get("errors") is not None:
            return False
        if parsed.get("message") and any(
            word in str(parsed.get("message")).lower()
            for word in ("error", "invalid", "not found", "forbidden", "unauthorized")
        ):
            return False
    lower_text = text.lower()
    if any(marker in lower_text for marker in PLACEHOLDER_MARKERS):
        return False
    return True


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def existing_success_response(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        old = json.loads(path.read_text())
    except Exception:
        return False
    status = old.get("http_status")
    return bool(old.get("ok")) and isinstance(status, int) and 200 <= status < 400


def write_status_matrix(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    lines = [
        "# RPC Fixture Recording Status",
        "",
        "| chain | family | method | modes | status | http | fixture |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {chain} | {family} | `{method}` | {modes} | {status} | {http} | `{fixture}` |".format(
                chain=row["chain"],
                family=row["family"],
                method=row["method"],
                modes=",".join(row["modes"]),
                status=row["status"],
                http=row.get("http_status") or "",
                fixture=row.get("fixture", ""),
            )
        )
    (output_dir / "status-matrix.md").write_text("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chains", default="all", help="Comma-separated chain names, or all")
    parser.add_argument("--modes", default="single,mixed", help="Comma-separated: single,mixed")
    parser.add_argument("--rpc-url", help="Override endpoint URL for all selected chains")
    parser.add_argument("--address", help="Override address/tx placeholder for all selected methods")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--fixtures-dir", default=str(DEFAULT_FIXTURES_DIR))
    parser.add_argument("--record", action="store_true", help="Send requests and save responses")
    parser.add_argument("--write-fake-node-fixtures", action="store_true", help="Copy response bytes into fake-node fixtures")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--delay", type=float, default=0.0, help="Delay between network requests")
    parser.add_argument("--limit-methods", type=int, default=0, help="Limit methods per chain for smoke runs")
    parser.add_argument("--health-probes", action="store_true", help="Record adapter health probes instead of benchmark RPC methods")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    fixtures_dir = Path(args.fixtures_dir)
    modes = {m.strip().lower() for m in args.modes.split(",") if m.strip()}
    rows: list[dict[str, Any]] = []
    fixture_maps: dict[str, dict[str, str]] = {}

    for chain in chain_names(args.chains):
        tpl_path = CHAINS_DIR / f"{chain}.json"
        if not tpl_path.exists():
            rows.append({"chain": chain, "family": "", "method": "", "modes": [], "status": "missing-template"})
            continue
        tpl = load_json(tpl_path)
        family = tpl.get("_meta", {}).get("adapter_family", "")
        fixture_map = fixture_maps.setdefault(family, load_fixture_map(family))
        endpoint = choose_endpoint(tpl, args.rpc_url)
        address = choose_address(tpl, args.address)
        methods = configured_methods(tpl, modes)
        if args.limit_methods:
            methods = methods[: args.limit_methods]
        if args.health_probes:
            methods = [{"method": "<health-probe>", "modes": ["health"], "weight": 0}]

        for item in methods:
            method = item["method"]
            row = {
                "chain": chain,
                "family": family,
                "method": method,
                "modes": item["modes"],
                "weight": item.get("weight", 1),
                "fixture": f"{chain}/{fixture_map.get(method, safe_name(method) + '.json')}",
            }
            if not endpoint:
                row["status"] = "missing-endpoint"
                rows.append(row)
                continue
            try:
                if args.health_probes:
                    method, request_data = build_health_request(chain, endpoint)
                    row["method"] = method
                    row["fixture"] = f"{chain}/{fixture_map.get(method, safe_name(method) + '.json')}"
                else:
                    request_data = build_request(chain, tpl, method, endpoint, address)
            except Exception as exc:
                row["status"] = "request-build-failed"
                row["error"] = str(exc)
                rows.append(row)
                continue
            method_dir = output_dir / chain / safe_name(method)

            meta = {
                "chain": chain,
                "family": family,
                "method": method,
                "modes": item["modes"],
                "weight": item.get("weight", 1),
                "endpoint": endpoint,
                "address": address,
                "recorded": bool(args.record),
                "fixture": row["fixture"],
            }
            write_json(method_dir / "request.json", request_data)
            write_json(method_dir / "meta.json", meta)

            if args.record:
                response = send_request(request_data, args.timeout)
                response_path = method_dir / "response.json"
                if response.get("ok") or not existing_success_response(response_path):
                    write_json(response_path, response)
                row["status"] = "recorded" if response.get("ok") else "record-failed"
                row["http_status"] = response.get("http_status")
                if args.write_fake_node_fixtures and response.get("ok") and response.get("body_text"):
                    fixture_name = fixture_map.get(method, f"{safe_name(method)}.json")
                    fixture_path = fixtures_dir / chain / fixture_name
                    fixture_path.parent.mkdir(parents=True, exist_ok=True)
                    fixture_path.write_text(response["body_text"])
                    row["fixture"] = str(fixture_path.relative_to(fixtures_dir))
                if args.delay:
                    time.sleep(args.delay)
            else:
                row["status"] = "dry-run"
            rows.append(row)

    write_json(output_dir / "manifest.json", rows)
    write_status_matrix(output_dir, rows)

    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    print(json.dumps({"total": len(rows), "statuses": status_counts}, indent=2, sort_keys=True))
    return 1 if any(r["status"].endswith("failed") for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
