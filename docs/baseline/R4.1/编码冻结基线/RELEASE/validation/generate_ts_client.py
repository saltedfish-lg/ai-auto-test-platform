#!/usr/bin/env python3
from pathlib import Path
import argparse, json, re, yaml

def ts_type(schema, name_hint="Anonymous"):
    if not isinstance(schema,dict): return "unknown"
    if "$ref" in schema: return schema["$ref"].split("/")[-1]
    if "enum" in schema: return " | ".join(json.dumps(x,ensure_ascii=False) for x in schema["enum"])
    if "oneOf" in schema: return " | ".join(ts_type(x,name_hint) for x in schema["oneOf"])
    if "anyOf" in schema: return " | ".join(ts_type(x,name_hint) for x in schema["anyOf"])
    if "allOf" in schema: return " & ".join(ts_type(x,name_hint) for x in schema["allOf"])
    t=schema.get("type")
    if isinstance(t,list):
        parts=[ts_type({**schema,"type":x},name_hint) for x in t]
        return " | ".join(dict.fromkeys(parts))
    if t=="string": return "string"
    if t in {"integer","number"}: return "number"
    if t=="boolean": return "boolean"
    if t=="null": return "null"
    if t=="array": return f"Array<{ts_type(schema.get('items',{}),name_hint+'Item')}>"
    if t=="object" or "properties" in schema:
        props=schema.get("properties",{})
        req=set(schema.get("required",[]))
        if not props:
            ap=schema.get("additionalProperties")
            return f"Record<string, {ts_type(ap,name_hint+'Value')}>" if isinstance(ap,dict) else "Record<string, unknown>"
        fields=[]
        for k,v in props.items():
            safe=k if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$",k) else json.dumps(k)
            fields.append(f"  {safe}{'' if k in req else '?'}: {ts_type(v,name_hint+k.title())};")
        return "{\n"+"\n".join(fields)+"\n}"
    return "unknown"

def schema_ref_name(node):
    if not isinstance(node,dict): return None
    if "$ref" in node and node["$ref"].startswith("#/components/schemas/"): return node["$ref"].split("/")[-1]
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[3])
    ap.add_argument("--out",type=Path)
    args=ap.parse_args()
    api=yaml.safe_load((args.root/"编码冻结基线/OPENAPI/openapi.yaml").read_text(encoding="utf-8"))
    out=args.out or Path(__file__).resolve().parent/"generated"
    out.mkdir(parents=True,exist_ok=True)
    comps=api["components"]["schemas"]
    lines=["/* Generated from PDBR-2026.08.06-R4.1 OpenAPI. DO NOT EDIT. */",""]
    for name,s in comps.items():
        lines.append(f"export type {name} = {ts_type(s,name)};")
    (out/"types.ts").write_text("\n\n".join(lines)+"\n",encoding="utf-8")
    imports=", ".join(comps.keys())
    client=["/* Generated from PDBR-2026.08.06-R4.1 OpenAPI. DO NOT EDIT. */",
            "import type { "+imports+" } from './types.js';",
            "export type RequestOptions = { headers?: Record<string,string>; signal?: AbortSignal };",
            "export class ApiClient {",
            "  constructor(private readonly baseUrl: string, private readonly fetcher: typeof fetch = fetch) {}",
            "  private async request<T>(path: string, init: RequestInit): Promise<T> {",
            "    const response = await this.fetcher(`${this.baseUrl}${path}`, init);",
            "    if (!response.ok) throw new Error(`HTTP ${response.status}`);",
            "    return (await response.json()) as T;",
            "  }"]
    methods={"get","post","put","patch","delete","head","options"}
    count=0
    for path,item in api["paths"].items():
        for method,op in item.items():
            if method.lower() not in methods or not isinstance(op,dict): continue
            opid=op["operationId"]
            req="unknown"
            rb=op.get("requestBody",{}).get("content",{}).get("application/json",{}).get("schema")
            if rb:
                req=schema_ref_name(rb) or ts_type(rb,opid+"Request")
            resp="unknown"
            for code in ["200","201","202","204","default"]:
                rs=op.get("responses",{}).get(code)
                if not rs: continue
                sch=rs.get("content",{}).get("application/json",{}).get("schema")
                if sch:
                    resp=schema_ref_name(sch) or ts_type(sch,opid+"Response")
                    break
            placeholders=re.findall(r"\{([^}]+)\}",path)
            argspec=[f"{p}: string" for p in placeholders]
            if rb: argspec.append(f"body: {req}")
            argspec.append("options: RequestOptions = {}")
            expr=json.dumps(path)
            for p in placeholders:
                expr=f"{expr}.replace('{{{p}}}', encodeURIComponent({p}))"
            bodyline=f", body: JSON.stringify(body)" if rb else ""
            client.append(f"  async {opid}({', '.join(argspec)}): Promise<{resp}> {{")
            client.append(f"    const path = {expr};")
            client.append(f"    return this.request<{resp}>(path, {{ method: '{method.upper()}', headers: {{ 'Content-Type': 'application/json', ...(options.headers ?? {{}}) }}, signal: options.signal{bodyline} }});")
            client.append("  }")
            count+=1
    client.append("}")
    (out/"client.ts").write_text("\n".join(client)+"\n",encoding="utf-8")
    report={"release_id":"PDBR-2026.08.06-R4.1","schema_types":len(comps),"client_methods":count,"outputs":["types.ts","client.ts"]}
    (out/"generation-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__": main()
