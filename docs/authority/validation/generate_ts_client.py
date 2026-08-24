#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

import yaml


def ts_type(schema, name_hint="Anonymous"):
    if not isinstance(schema, dict):
        return "unknown"
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    if "const" in schema:
        return json.dumps(schema["const"], ensure_ascii=False)
    if "enum" in schema:
        return " | ".join(json.dumps(x, ensure_ascii=False) for x in schema["enum"])
    if "oneOf" in schema:
        return " | ".join(ts_type(x, name_hint) for x in schema["oneOf"])
    if "anyOf" in schema:
        return " | ".join(ts_type(x, name_hint) for x in schema["anyOf"])
    if "allOf" in schema:
        return " & ".join(ts_type(x, name_hint) for x in schema["allOf"])
    t = schema.get("type")
    if isinstance(t, list):
        parts = [ts_type({**schema, "type": x}, name_hint) for x in t]
        return " | ".join(dict.fromkeys(parts))
    if t == "string":
        return "string"
    if t in {"integer", "number"}:
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "null":
        return "null"
    if t == "array":
        return f"Array<{ts_type(schema.get('items', {}), name_hint + 'Item')}>"
    if t == "object" or "properties" in schema:
        props = schema.get("properties", {})
        req = set(schema.get("required", []))
        if not props:
            ap = schema.get("additionalProperties")
            if isinstance(ap, dict):
                return f"Record<string, {ts_type(ap, name_hint + 'Value')}>"
            if ap is False or schema.get("maxProperties") == 0:
                return "Record<string, never>"
            return "Record<string, unknown>"
        fields = []
        for k, v in props.items():
            safe = k if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", k) else json.dumps(k)
            fields.append(
                f"  {safe}{'' if k in req else '?'}: {ts_type(v, name_hint + k.title())};"
            )
        return "{\n" + "\n".join(fields) + "\n}"
    return "unknown"


def schema_ref_name(node):
    if not isinstance(node, dict):
        return None
    if "$ref" in node and node["$ref"].startswith("#/components/schemas/"):
        return node["$ref"].split("/")[-1]
    return None


def success_response_type(operation):
    """Return the union of declared successful response bodies, including bodyless responses."""
    response_types = []
    for code, response in operation.get("responses", {}).items():
        if not (isinstance(code, str) and code.isdigit() and 200 <= int(code) < 300):
            continue
        schema = response.get("content", {}).get("application/json", {}).get("schema")
        response_type = (schema_ref_name(schema) or ts_type(schema)) if schema else "void"
        if response_type not in response_types:
            response_types.append(response_type)
    return " | ".join(response_types) if response_types else "unknown"


def required_header_names(path_item, operation):
    """Collect required header parameters from both path-item and operation scopes."""
    parameters = [*path_item.get("parameters", []), *operation.get("parameters", [])]
    return [
        parameter["name"]
        for parameter in parameters
        if isinstance(parameter, dict)
        and parameter.get("in") == "header"
        and parameter.get("required") is True
    ]


def resolved_parameters(api, path_item, operation):
    """Resolve local component parameters while preserving path-item/operation order."""
    resolved = []
    for parameter in [*path_item.get("parameters", []), *operation.get("parameters", [])]:
        if not isinstance(parameter, dict):
            continue
        ref = parameter.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/parameters/"):
            parameter = api.get("components", {}).get("parameters", {}).get(
                ref.split("/")[-1], {}
            )
        if isinstance(parameter, dict):
            resolved.append(parameter)
    return resolved


def query_parameters(api, path_item, operation):
    """Collect unique query parameters declared by the current OpenAPI operation."""
    by_name = {}
    for parameter in resolved_parameters(api, path_item, operation):
        if parameter.get("in") == "query" and isinstance(parameter.get("name"), str):
            by_name[parameter["name"]] = parameter
    return list(by_name.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    api = yaml.safe_load(
        (args.root / "编码权威事实/OPENAPI/openapi.yaml").read_text(encoding="utf-8")
    )
    out = args.out or Path(__file__).resolve().parent / "generated"
    out.mkdir(parents=True, exist_ok=True)
    comps = api["components"]["schemas"]
    lines = ["/* Generated from current docs/authority OpenAPI. DO NOT EDIT. */", ""]
    for name, s in comps.items():
        lines.append(f"export type {name} = {ts_type(s, name)};")
    (out / "types.ts").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    imports = ", ".join(comps.keys())
    client = [
        "/* Generated from current docs/authority OpenAPI. DO NOT EDIT. */",
        "import type { " + imports + " } from './types.js';",
        "export type RequestOptions = { headers?: Record<string,string>; signal?: AbortSignal };",
        "export type QueryRequestOptions<Q extends Record<string, unknown>> = "
        "RequestOptions & { query?: Q };",
        "export type RequiredHeaderOptions<K extends string> = "
        "Omit<RequestOptions, 'headers'> & "
        "{ headers: Record<string,string> & Record<K,string> };",
        "export type RequiredHeaderQueryOptions<K extends string, Q extends Record<string, unknown>> = "
        "RequiredHeaderOptions<K> & { query?: Q };",
        "export class ApiClient {",
        "  constructor(private readonly baseUrl: string, "
        "private readonly fetcher: typeof fetch = fetch) {}",
        "  private async request<T>(path: string, init: RequestInit): Promise<T> {",
        "    const response = await this.fetcher(`${this.baseUrl}${path}`, init);",
        "    if (!response.ok) throw new Error(`HTTP ${response.status}`);",
        "    if (response.status === 204) return undefined as T;",
        "    return (await response.json()) as T;",
        "  }",
    ]
    methods = {"get", "post", "put", "patch", "delete", "head", "options"}
    count = 0
    for path, item in api["paths"].items():
        for method, op in item.items():
            if method.lower() not in methods or not isinstance(op, dict):
                continue
            opid = op["operationId"]
            req = "unknown"
            request_body = op.get("requestBody", {})
            rb = (
                request_body
                .get("content", {})
                .get("application/json", {})
                .get("schema")
            )
            if rb:
                req = schema_ref_name(rb) or ts_type(rb, opid + "Request")
            resp = success_response_type(op)
            placeholders = re.findall(r"\{([^}]+)\}", path)
            argspec = [f"{p}: string" for p in placeholders]
            if rb:
                body_marker = "" if request_body.get("required") is True else "?"
                argspec.append(f"body{body_marker}: {req}")
            required_headers = required_header_names(item, op)
            query = query_parameters(api, item, op)
            query_type = None
            if query:
                fields = []
                for parameter in query:
                    name = parameter["name"]
                    safe = name if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", name) else json.dumps(name)
                    marker = "" if parameter.get("required") is True else "?"
                    fields.append(f"{safe}{marker}: {ts_type(parameter.get('schema', {}), opid + name.title())}")
                query_type = "{ " + "; ".join(fields) + " }"
            if required_headers:
                header_keys = " | ".join(json.dumps(name) for name in required_headers)
                options_type = f"RequiredHeaderOptions<{header_keys}>"
                if query_type:
                    options_type = f"RequiredHeaderQueryOptions<{header_keys}, {query_type}>"
                argspec.append(f"options: {options_type}")
            else:
                options_type = f"QueryRequestOptions<{query_type}>" if query_type else "RequestOptions"
                argspec.append(f"options: {options_type} = {{}}")
            expr = json.dumps(path)
            for p in placeholders:
                expr = f"{expr}.replace('{{{p}}}', encodeURIComponent({p}))"
            if rb and request_body.get("required") is True:
                bodyline = ", body: JSON.stringify(body)"
            elif rb:
                bodyline = ", ...(body === undefined ? {} : { body: JSON.stringify(body) })"
            else:
                bodyline = ""
            client.append(f"  async {opid}({', '.join(argspec)}): Promise<{resp}> {{")
            client.append(f"    let path = {expr};")
            if query:
                client.append("    const query = new URLSearchParams();")
                for parameter in query:
                    name = parameter["name"]
                    access = name if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", name) else f"[{json.dumps(name)}]"
                    if access.startswith("["):
                        value = f"options.query?.{access}"
                    else:
                        value = f"options.query?.{access}"
                    client.append(
                        f"    if ({value} !== undefined) query.set({json.dumps(name)}, String({value}));"
                    )
                client.append("    const encodedQuery = query.toString();")
                client.append("    if (encodedQuery) path += `?${encodedQuery}`;")
            client.append(
                f"    return this.request<{resp}>(path, "
                f"{{ method: '{method.upper()}', "
                "headers: { 'Content-Type': 'application/json', "
                f"...(options.headers ?? {{}}) }}, signal: options.signal{bodyline} }});"
            )
            client.append("  }")
            count += 1
    client.append("}")
    (out / "client.ts").write_text("\n".join(client) + "\n", encoding="utf-8")
    report = {
        "authority_model": "SINGLE_LIVING_AUTHORITY",
        "authority_root": "docs/authority",
        "schema_types": len(comps),
        "client_methods": count,
        "outputs": ["types.ts", "client.ts"],
    }
    (out / "generation-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
