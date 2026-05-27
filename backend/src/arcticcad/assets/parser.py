from __future__ import annotations

import json
import math
import re
import struct
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from arcticcad.domain import AssetEntitySummary, AssetSummary


@dataclass(frozen=True)
class ParsedAsset:
    summary: AssetSummary
    raw_script: str | None = None
    error: str | None = None


def parse_asset(path: Path, asset_format: str, project_root: Path) -> ParsedAsset:
    if asset_format == "dxf":
        return _parse_dxf(path, project_root)
    if asset_format == "stl":
        return _parse_stl(path, project_root)
    return ParsedAsset(
        summary=AssetSummary(format="dxf", warnings=[f"Unsupported asset format: {asset_format}"]),
        error=f"Unsupported asset format: {asset_format}",
    )


def _parse_with_node(path: Path, asset_format: str, project_root: Path) -> tuple[AssetSummary | None, str | None, str | None]:
    adapter = Path(__file__).with_name("jscad_adapter.cjs")
    raw_script_path = path.parent / "converted.raw.js"
    node_path = project_root / "frontend" / "node_modules"
    command = ["node", str(adapter), asset_format, str(path), str(raw_script_path)]
    try:
        completed = subprocess.run(
            command,
            cwd=project_root / "frontend",
            env={**_node_env(node_path)},
            capture_output=True,
            check=False,
            timeout=30,
        )
    except Exception as exc:
        return None, None, f"JSCAD adapter unavailable: {exc}"
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    if completed.returncode != 0:
        return None, None, stderr.strip() or stdout.strip()
    try:
        payload = json.loads(stdout or "{}")
        summary = AssetSummary.model_validate(payload.get("summary") or {})
        raw_script = payload.get("rawScript")
        if raw_script is None and raw_script_path.exists():
            raw_script = raw_script_path.read_text(encoding="utf-8")
        return summary, raw_script, None
    except Exception as exc:
        return None, None, f"JSCAD adapter returned invalid JSON: {exc}"


def _node_env(node_path: Path) -> dict[str, str]:
    import os

    env = dict(os.environ)
    existing = env.get("NODE_PATH", "")
    env["NODE_PATH"] = str(node_path) if not existing else f"{node_path}{os.pathsep}{existing}"
    return env


def _parse_dxf(path: Path, project_root: Path) -> ParsedAsset:
    text = path.read_text(encoding="utf-8", errors="replace")
    fallback = _summarize_ascii_dxf(text)
    node_summary, raw_script, node_error = _parse_with_node(path, "dxf", project_root)
    warnings = list(fallback.warnings)
    if node_error:
        warnings.append(f"OpenJSCAD DXF 解析未完成：{_short_error(node_error)}")
    if node_summary:
        merged = fallback.model_copy(
            update={
                "bounds": fallback.bounds or node_summary.bounds,
                "rawScriptPath": "converted.raw.js" if raw_script else None,
                "warnings": warnings + node_summary.warnings,
            }
        )
        return ParsedAsset(summary=merged, raw_script=raw_script)
    return ParsedAsset(summary=fallback.model_copy(update={"warnings": warnings}), raw_script=raw_script, error=None)


def _summarize_ascii_dxf(text: str) -> AssetSummary:
    if "\x00" in text[:1024]:
        return AssetSummary(format="dxf", warnings=["DXF appears to be binary; only ASCII DXF is supported for entity extraction."])
    pairs = _dxf_pairs(text)
    layers: set[str] = set()
    entities: list[AssetEntitySummary] = []
    counts: Counter[str] = Counter()
    i = 0
    entity_id = 0
    while i < len(pairs):
        code, value = pairs[i]
        if code != "0":
            i += 1
            continue
        kind = value.upper()
        if kind not in {"LINE", "CIRCLE", "ARC", "LWPOLYLINE", "POLYLINE"}:
            i += 1
            continue
        data: dict[str, list[str]] = {}
        i += 1
        while i < len(pairs) and pairs[i][0] != "0":
            data.setdefault(pairs[i][0], []).append(pairs[i][1])
            i += 1
        layer = _first(data, "8") or "0"
        layers.add(layer)
        counts[kind] += 1
        entity_id += 1
        entity = _entity_from_dxf(kind, data, layer, f"entity-{entity_id}")
        if entity:
            entities.append(entity)
    bounds = _bounds_for_entities(entities)
    closed_profiles = [
        {"entityId": entity.id, "layer": entity.layer, "pointCount": len(entity.points), "bounds": entity.bounds}
        for entity in entities
        if entity.closed
    ]
    return AssetSummary(
        format="dxf",
        units="millimeters",
        bounds=bounds,
        layers=sorted(layers),
        entityCounts=dict(counts),
        entities=entities[:200],
        closedProfiles=closed_profiles[:80],
        warnings=[],
    )


def _dxf_pairs(text: str) -> list[tuple[str, str]]:
    lines = [line.strip() for line in text.splitlines()]
    pairs: list[tuple[str, str]] = []
    for index in range(0, len(lines) - 1, 2):
        pairs.append((lines[index], lines[index + 1]))
    return pairs


def _entity_from_dxf(kind: str, data: dict[str, list[str]], layer: str, entity_id: str) -> AssetEntitySummary | None:
    if kind == "LINE":
        points = [[_float(_first(data, "10")), _float(_first(data, "20"))], [_float(_first(data, "11")), _float(_first(data, "21"))]]
        return AssetEntitySummary(id=entity_id, type="LINE", layer=layer, points=points, bounds=_bounds(points))
    if kind == "CIRCLE":
        center = [_float(_first(data, "10")), _float(_first(data, "20"))]
        radius = _float(_first(data, "40"))
        bounds = {"min": [center[0] - radius, center[1] - radius], "max": [center[0] + radius, center[1] + radius]}
        return AssetEntitySummary(id=entity_id, type="CIRCLE", layer=layer, center=center, radius=radius, closed=True, bounds=bounds)
    if kind == "ARC":
        center = [_float(_first(data, "10")), _float(_first(data, "20"))]
        radius = _float(_first(data, "40"))
        return AssetEntitySummary(
            id=entity_id,
            type="ARC",
            layer=layer,
            center=center,
            radius=radius,
            startAngle=_float(_first(data, "50")),
            endAngle=_float(_first(data, "51")),
            bounds={"min": [center[0] - radius, center[1] - radius], "max": [center[0] + radius, center[1] + radius]},
        )
    if kind in {"LWPOLYLINE", "POLYLINE"}:
        xs = [_float(value) for value in data.get("10", [])]
        ys = [_float(value) for value in data.get("20", [])]
        points = [[x, ys[index] if index < len(ys) else 0.0] for index, x in enumerate(xs)]
        flags = int(_float(_first(data, "70")))
        closed = bool(flags & 1) or (len(points) > 2 and _same_point(points[0], points[-1]))
        return AssetEntitySummary(id=entity_id, type=kind, layer=layer, points=points, closed=closed, bounds=_bounds(points))
    return None


def _parse_stl(path: Path, project_root: Path) -> ParsedAsset:
    node_summary, _, node_error = _parse_with_node(path, "stl", project_root)
    fallback = _summarize_stl(path)
    warnings = list(fallback.warnings)
    if node_error:
        warnings.append(f"OpenJSCAD STL 解析未完成：{_short_error(node_error)}")
    if node_summary:
        summary = fallback.model_copy(
            update={
                "bounds": node_summary.bounds or fallback.bounds,
                "triangleCount": node_summary.triangleCount or fallback.triangleCount,
                "solidCount": node_summary.solidCount or fallback.solidCount,
                "warnings": warnings + node_summary.warnings,
            }
        )
        return ParsedAsset(summary=summary)
    return ParsedAsset(summary=fallback.model_copy(update={"warnings": warnings}), error=None)


def _summarize_stl(path: Path) -> AssetSummary:
    data = path.read_bytes()
    if _looks_ascii_stl(data):
        return _summarize_ascii_stl(data.decode("utf-8", errors="replace"))
    return _summarize_binary_stl(data)


def _looks_ascii_stl(data: bytes) -> bool:
    sample = data[:512].lstrip()
    return sample.lower().startswith(b"solid") and b"facet" in data[:4096].lower()


def _summarize_ascii_stl(text: str) -> AssetSummary:
    points = [
        [float(x), float(y), float(z)]
        for x, y, z in re.findall(
            r"\bvertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)",
            text,
        )
    ]
    solid_count = len(re.findall(r"\bsolid\b", text, flags=re.IGNORECASE)) or 1
    return AssetSummary(
        format="stl",
        bounds=_bounds(points),
        triangleCount=len(points) // 3,
        solidCount=solid_count,
        isLikelyWatertight=None,
        warnings=["STL 已作为网格参考解析；不会自动展开为主 JSCAD polyhedron 代码。"],
    )


def _summarize_binary_stl(data: bytes) -> AssetSummary:
    points: list[list[float]] = []
    triangle_count = 0
    if len(data) >= 84:
        triangle_count = struct.unpack_from("<I", data, 80)[0]
        offset = 84
        for _ in range(min(triangle_count, 200000)):
            if offset + 50 > len(data):
                break
            offset += 12
            for _vertex in range(3):
                points.append(list(struct.unpack_from("<fff", data, offset)))
                offset += 12
            offset += 2
    return AssetSummary(
        format="stl",
        bounds=_bounds(points),
        triangleCount=triangle_count,
        solidCount=1 if triangle_count else 0,
        isLikelyWatertight=None,
        warnings=["STL 已作为网格参考解析；不会自动展开为主 JSCAD polyhedron 代码。"],
    )


def _bounds_for_entities(entities: list[AssetEntitySummary]) -> dict[str, list[float]] | None:
    points: list[list[float]] = []
    for entity in entities:
        if entity.points:
            points.extend(entity.points)
        if entity.bounds:
            points.append(entity.bounds["min"])
            points.append(entity.bounds["max"])
    return _bounds(points)


def _bounds(points: list[list[float]]) -> dict[str, list[float]] | None:
    clean = [[value for value in point if math.isfinite(value)] for point in points if point]
    clean = [point for point in clean if point]
    if not clean:
        return None
    dimensions = max(len(point) for point in clean)
    mins = [min((point[index] if index < len(point) else 0.0) for point in clean) for index in range(dimensions)]
    maxs = [max((point[index] if index < len(point) else 0.0) for point in clean) for index in range(dimensions)]
    return {"min": mins, "max": maxs}


def _first(data: dict[str, list[str]], code: str) -> str | None:
    values = data.get(code)
    return values[0] if values else None


def _float(value: str | None) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def _same_point(a: list[float], b: list[float]) -> bool:
    return len(a) == len(b) and all(abs(left - right) < 1e-6 for left, right in zip(a, b))


def _short_error(value: str) -> str:
    first_line = value.splitlines()[0] if value.splitlines() else value
    return first_line[:240]
