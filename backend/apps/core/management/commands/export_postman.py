"""
Export the API as a Postman collection (v2.1), generated from the same OpenAPI schema as Swagger, so it never drifts:

    python manage.py export_postman                       # -> docs/postman_collection.json
    python manage.py export_postman --output my.json

One folder per Swagger tag; every request uses the collection variables {{base_url}} (default
http://localhost:8000) and {{access_token}} (Bearer auth; public endpoints send it harmlessly). Request bodies are
filled with an example built from the schema (types, enums and formats), ready to edit.
"""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from drf_spectacular.generators import SchemaGenerator

METHODS = ("get", "post", "put", "patch", "delete")
MAX_DEPTH = 4


def _resolve(schema, components):
    while isinstance(schema, dict) and "$ref" in schema:
        schema = components.get(schema["$ref"].split("/")[-1], {})
    return schema or {}


def example(schema, components, depth=0):
    """A plausible example value for a JSON schema (refs, allOf/oneOf, objects, arrays, enums, formats)."""
    schema = _resolve(schema, components)
    if depth > MAX_DEPTH:
        return None
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    for key in ("allOf", "oneOf", "anyOf"):
        if schema.get(key):
            parts = [example(s, components, depth + 1) for s in schema[key]]
            merged = {}
            for part in parts:
                if isinstance(part, dict):
                    merged.update(part)
                elif part is not None and not merged:
                    return part
            return merged
    if "enum" in schema:
        values = [v for v in schema["enum"] if v not in (None, "")]
        return values[0] if values else ""
    kind = schema.get("type")
    if kind == "object" or "properties" in schema:
        props = schema.get("properties", {})
        return {name: example(prop, components, depth + 1) for name, prop in props.items() if not _resolve(prop, components).get("readOnly")}
    if kind == "array":
        return [example(schema.get("items", {}), components, depth + 1)]
    if kind == "integer":
        return 1
    if kind == "number":
        return 0
    if kind == "boolean":
        return False
    fmt = schema.get("format", "")
    return {
        "date": "2026-01-31", "date-time": "2026-01-31T10:00:00+06:00", "email": "customer@example.com",
        "uri": "https://example.com", "decimal": "100.00", "binary": "",
    }.get(fmt, "string")


def to_postman(schema):
    components = schema.get("components", {}).get("schemas", {})
    folders = {}
    for path, operations in schema.get("paths", {}).items():
        for method in METHODS:
            op = operations.get(method)
            if not op:
                continue
            tag = (op.get("tags") or ["Other"])[0]
            segments = [f":{s[1:-1]}" if s.startswith("{") else s for s in path.strip("/").split("/")]
            query = [
                {"key": p["name"], "value": "", "description": p.get("description", ""), "disabled": True}
                for p in op.get("parameters", []) if p.get("in") == "query"
            ]
            variables = [{"key": p["name"], "value": "1"} for p in op.get("parameters", []) if p.get("in") == "path"]
            request = {
                "method": method.upper(),
                "header": [],
                "url": {"raw": "{{base_url}}/" + "/".join(segments) + "/", "host": ["{{base_url}}"], "path": [*segments, ""],
                        "query": query, "variable": variables},
                "description": op.get("description", ""),
            }
            content = op.get("requestBody", {}).get("content", {})
            if "application/json" in content:
                body = example(content["application/json"].get("schema", {}), components)
                request["header"].append({"key": "Content-Type", "value": "application/json"})
                request["body"] = {"mode": "raw", "raw": json.dumps(body, indent=2, ensure_ascii=False)}
            elif "multipart/form-data" in content:
                props = _resolve(content["multipart/form-data"].get("schema", {}), components).get("properties", {})
                request["body"] = {"mode": "formdata", "formdata": [
                    {"key": name, "type": "file" if _resolve(prop, components).get("format") == "binary" else "text", "value": ""}
                    for name, prop in props.items() if not _resolve(prop, components).get("readOnly")
                ]}
            folders.setdefault(tag, []).append({"name": op.get("summary") or f"{method.upper()} {path}", "request": request})

    info = schema.get("info", {})
    return {
        "info": {
            "name": info.get("title", "API"), "description": info.get("description", ""),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{access_token}}", "type": "string"}]},
        "variable": [{"key": "base_url", "value": "http://localhost:8000"}, {"key": "access_token", "value": ""}],
        "item": [{"name": tag, "item": items} for tag, items in folders.items()],
    }


class Command(BaseCommand):
    help = "Export the OpenAPI schema as a Postman v2.1 collection (default: docs/postman_collection.json)."

    def add_arguments(self, parser):
        parser.add_argument("--output", default=str(Path(settings.BASE_DIR) / "docs" / "postman_collection.json"))

    def handle(self, *args, output, **options):
        schema = SchemaGenerator().get_schema(request=None, public=True)
        collection = to_postman(json.loads(json.dumps(schema, default=str)))
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(collection, indent=2, ensure_ascii=False), encoding="utf-8")
        count = sum(len(folder["item"]) for folder in collection["item"])
        self.stdout.write(self.style.SUCCESS(f"Wrote {count} requests in {len(collection['item'])} folders to {path}"))
