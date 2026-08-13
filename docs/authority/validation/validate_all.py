#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse, csv, hashlib, json, re, sys
from collections import Counter, defaultdict
from typing import Any
import yaml

YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

def _yaml_load(text: str):
    return yaml.load(text, Loader=YAML_LOADER)
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))
from current_facts import derive_current_facts, discover_migrations  # noqa: E402

AUTHORITY_MODEL = "SINGLE_LIVING_AUTHORITY"
AUTHORITY_ROOT_NAME = "authority"
EXPECTED_CODE_READINESS = "READY_FOR_P1_IMPLEMENTATION"

class Validation:
    def __init__(self, root: Path):
        self.root = root
        self.checks: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.metrics: dict[str, Any] = {}
        self._yaml_cache: dict[str, Any] = {}
        self._json_cache: dict[str, Any] = {}
    def add(self, name: str, passed: bool, detail: str, errors: list[str] | None = None):
        errs = errors or []
        self.checks.append({"check": name, "status": "PASS" if passed else "FAIL", "detail": detail, "errors": errs})
        if not passed:
            self.errors.extend(f"{name}: {e}" for e in errs or [detail])
    def yaml(self, rel: str):
        if rel not in self._yaml_cache:
            self._yaml_cache[rel] = _yaml_load((self.root/rel).read_text(encoding="utf-8"))
        return self._yaml_cache[rel]
    def json(self, rel: str):
        if rel not in self._json_cache:
            self._json_cache[rel] = json.loads((self.root/rel).read_text(encoding="utf-8"))
        return self._json_cache[rel]

def parse_create_tables(sql: str):
    tables = {}
    rx = re.compile(r"CREATE TABLE\s+`?([A-Za-z0-9_]+)`?\s*\((.*?)\)\s*ENGINE=", re.S|re.I)
    for table, body in rx.findall(sql):
        columns = {}
        pk = []
        uniques = []
        checks = []
        constraint_names = []
        for raw in body.splitlines():
            line=raw.strip().rstrip(",")
            if not line: continue
            m=re.match(r"`?([A-Za-z0-9_]+)`?\s+([A-Z]+(?:\([^)]+\))?)(.*)$",line,re.I)
            if m and m.group(1).upper() not in {"PRIMARY","CONSTRAINT","UNIQUE","CHECK","FOREIGN"}:
                name,typ,rest=m.groups()
                columns[name]={"type":typ.upper().replace(" ",""),"nullable":"NOT NULL" not in rest.upper(),
                               "default": (re.search(r"\bDEFAULT\s+('(?:[^']|'')*'|[A-Za-z0-9_().+-]+)",rest,re.I).group(1)
                                           if re.search(r"\bDEFAULT\s+('(?:[^']|'')*'|[A-Za-z0-9_().+-]+)",rest,re.I) else None)}
                continue
            m=re.search(r"PRIMARY KEY\s*\(([^)]+)\)",line,re.I)
            if m: pk=[x.strip(" `") for x in m.group(1).split(",")]
            m=re.search(r"CONSTRAINT\s+`?([A-Za-z0-9_]+)`?\s+UNIQUE\s*\(([^)]+)\)",line,re.I)
            if m:
                constraint_names.append(m.group(1)); uniques.append([x.strip(" `") for x in m.group(2).split(",")])
            m=re.search(r"CONSTRAINT\s+`?([A-Za-z0-9_]+)`?\s+CHECK\s*\((.*)\)",line,re.I)
            if m:
                constraint_names.append(m.group(1)); checks.append({"name":m.group(1),"expression":m.group(2)})
        tables[table]={"columns":columns,"pk":pk,"uniques":uniques,"checks":checks,"constraint_names":constraint_names}
    return tables

def parse_fks(sql: str):
    rx=re.compile(
      r"ALTER TABLE\s+`?([A-Za-z0-9_]+)`?\s+ADD CONSTRAINT\s+`?([A-Za-z0-9_]+)`?\s+"
      r"FOREIGN KEY\s*\(`?([A-Za-z0-9_]+)`?\)\s+REFERENCES\s+`?([A-Za-z0-9_]+)`?\s*"
      r"\(`?([A-Za-z0-9_]+)`?\)(?:\s+ON DELETE\s+([A-Z ]+?))?(?:\s+ON UPDATE\s+([A-Z ]+?))?;",re.I)
    out=[]
    for m in rx.finditer(sql):
        out.append({"child_table":m.group(1),"name":m.group(2),"child_column":m.group(3),
                    "parent_table":m.group(4),"parent_column":m.group(5),
                    "on_delete":(m.group(6) or "").strip(),"on_update":(m.group(7) or "").strip()})
    return out

def local_deref(schema: Any, components: dict[str,Any]):
    if isinstance(schema,dict):
        if "$ref" in schema and schema["$ref"].startswith("#/components/schemas/"):
            return local_deref(components[schema["$ref"].split("/")[-1]],components)
        return {k:local_deref(v,components) for k,v in schema.items() if k not in {"discriminator"}}
    if isinstance(schema,list): return [local_deref(v,components) for v in schema]
    return schema

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument("--output",type=Path)
    args=ap.parse_args()
    v=Validation(args.root)

    # 1 parse formal machine files (event schemas are validated in the event gate)
    parse_errors=[]
    for p in args.root.rglob("*"):
        if not p.is_file(): continue
        rel=p.relative_to(args.root).as_posix()
        if rel.startswith("编码权威事实/EVENT_CONTRACTS/schemas/"):
            continue
        try:
            if p.suffix in {".yaml",".yml"}: v.yaml(rel)
            elif p.suffix==".json": v.json(rel)
            elif p.suffix==".csv":
                with p.open(encoding="utf-8-sig",newline="") as f:
                    rows=list(csv.reader(f))
                    if rows:
                        n=len(rows[0])
                        if any(len(r)!=n for r in rows[1:]): raise ValueError("inconsistent CSV column count")
        except Exception as e: parse_errors.append(f"{rel}: {e}")
    v.add("FORMAL_PARSE",not parse_errors,f"parse errors={len(parse_errors)}",parse_errors[:50])

    # 2 current metadata and architecture
    formal=[
      "产品总体需求与系统边界/产品总体需求与系统边界.yaml",
      "用户角色、核心场景与模块菜单/用户角色、核心场景与模块菜单.yaml",
      "核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml",
      "权限、并发与资源冲突规则/权限、并发与资源冲突规则.yaml",
      "AI测试流程与Runner业务规则/AI测试流程与Runner业务规则.yaml",
      "数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml",
    ]
    meta_errors=[]
    for rel in formal:
        m=v.yaml(rel).get("metadata",{})
        for k in ["coding_readiness","platform_code_readiness","code_readiness"]:
            if k in m and m[k]!=EXPECTED_CODE_READINESS: meta_errors.append(f"{rel} {k}={m[k]}")
    arch_rel="系统技术架构技术选型与AGENTS/系统技术架构和技术栈、技术选型.yaml"
    arch_text=(args.root/arch_rel).read_text(encoding="utf-8")
    stale=["CANDIDATE_SELECTED_PENDING_BASELINE","PENDING_CURRENT_SYSTEM_DESIGN","VALID_ARCHITECTURE_COMPLETION_PENDING_CURRENT_SYSTEM_DESIGN"]
    for s in stale:
        if s in arch_text: meta_errors.append(f"architecture stale state: {s}")
    arch=v.yaml(arch_rel)
    # expected current architecture state
    if arch.get("architecture_style",{}).get("status")!="FROZEN": meta_errors.append("architecture_style.status is not FROZEN")
    if args.root.name != AUTHORITY_ROOT_NAME: meta_errors.append(f"authority root name={args.root.name}")
    v.add("GOVERNANCE_AND_ARCHITECTURE",not meta_errors,"living authority readiness and approved architecture",meta_errors)

    # 3 core identities and states
    core=v.yaml("核心对象、业务规则与生命周期/核心对象、业务规则与生命周期.yaml")
    objects={o["object_id"]:o for o in core["objects"]}
    id_errors=[]
    expected={"OBJ-014":("credential_revision_id","test_account_id+revision_no"),
              "OBJ-084":("technical_alert_endpoint_id","endpoint_code"),
              "OBJ-088":("technical_alert_ingestion_batch_id","technical_alert_endpoint_id+batch_key")}
    for oid,(pk,buk) in expected.items():
        o=objects[oid]
        if o.get("technical_identifier")!=pk:id_errors.append(f"{oid} technical_identifier={o.get('technical_identifier')}")
        if buk not in o.get("business_unique_keys",[]):id_errors.append(f"{oid} missing business key {buk}")
    dims=core["state_dimensions"]
    dim_ids=[d["state_dimension_id"] for d in dims]
    if len(dim_ids)!=len(set(dim_ids)):id_errors.append("duplicate state_dimension_id")
    for d in dims:
        if d.get("initial_value") not in d.get("values",[]):id_errors.append(f"{d['state_dimension_id']} initial outside values")
    run_dim=next(d for d in dims if d["state_dimension_id"]=="SD-EX-010")
    if run_dim["initial_value"]!="UNKNOWN":id_errors.append("SD-EX-010 initial is not UNKNOWN")
    # lifecycle stages and transitions in dimension values
    dim_by_id={d["state_dimension_id"]:d for d in dims}
    for lc in core.get("lifecycles",[]):
        if not lc.get("state_dimensions"): continue
        d=dim_by_id.get(lc["state_dimensions"][0])
        if not d: id_errors.append(f"{lc['lifecycle_id']} missing state dimension"); continue
        stages=[lc.get("initial_stage")]+lc.get("active_stages",[])+lc.get("suspended_stages",[])+lc.get("exception_stages",[])+lc.get("terminal_stages",[])
        for s in stages:
            if s and s not in d["values"]: id_errors.append(f"{lc['lifecycle_id']} stage {s} outside {d['state_dimension_id']}")
    for tr in core.get("lifecycle_transitions",[]):
        lc=next((x for x in core["lifecycles"] if x["lifecycle_id"]==tr["lifecycle_id"]),None)
        if lc and lc.get("state_dimensions"):
            d=dim_by_id[lc["state_dimensions"][0]]
            if tr["from_stage"] not in d["values"] or tr["to_stage"] not in d["values"]:
                id_errors.append(f"{tr['transition_id']} transition outside values")
    v.metrics["state_dimensions"]=len(dims)
    v.add("CORE_IDENTITY_STATE_LIFECYCLE",not id_errors,f"objects={len(objects)}, dimensions={len(dims)}",id_errors[:100])

    # 4 registry consistency
    reg=v.yaml("编码权威事实/STATE_OWNER_REGISTRY/state-owner-registry.yaml")
    reg_by={d["state_dimension_id"]:d for d in reg["state_owners"]}
    reg_errors=[]
    if len(reg_by)!=len(dims):reg_errors.append(f"registry {len(reg_by)} != core {len(dims)}")
    for did,d in dim_by_id.items():
        r=reg_by.get(did)
        if not r:reg_errors.append(f"missing {did}");continue
        for k in ["object_id","initial_value","values"]:
            if r.get(k)!=d.get(k):reg_errors.append(f"{did} mismatch {k}")
    v.add("STATE_OWNER_REGISTRY",not reg_errors,f"registry dimensions={len(reg_by)}",reg_errors[:100])

    # 5 DDL and schema: the current chain/head/counts are mechanically derived, never copied here.
    repo_root = args.root.parents[1]
    current_facts = derive_current_facts(repo_root)
    migrations = discover_migrations(args.root)
    sql = "\n".join(item["path"].read_text(encoding="utf-8") for item in migrations)
    tables=parse_create_tables(sql); fks=parse_fks(sql)
    for dropped in re.findall(r"DROP TABLE(?:\s+IF EXISTS)?\s+`?([A-Za-z0-9_]+)`?", sql, re.I):
        tables.pop(dropped, None)
    fks=[fk for fk in fks if fk["child_table"] in tables and fk["parent_table"] in tables]
    # V7 intentionally evolves the shared V3 idempotency table instead of creating a
    # parallel authentication table. Reflect only the explicitly parsed additive columns.
    v7_idempotency_columns = {
        "contract_version": {"type": "SMALLINT", "nullable": False, "default": "2"},
        "principal_id": {"type": "VARCHAR(26)", "nullable": True, "default": None},
        "completed_at": {"type": "DATETIME(6)", "nullable": True, "default": None},
    }
    idempotency_columns = tables.get("atp_idempotency_record", {}).get("columns", {})
    for column, expected_column in v7_idempotency_columns.items():
        if not re.search(rf"ADD COLUMN\s+{column}\s+", sql, re.I):
            continue
        idempotency_columns[column] = expected_column
    ddl_errors=[]
    if len(tables)!=current_facts["database"]["table_count"]:ddl_errors.append(f"current table count={len(tables)}; derived={current_facts["database"]["table_count"]}")
    # columns and PK
    for tn,t in tables.items():
        if len(t["columns"])!=len(set(t["columns"])):ddl_errors.append(f"{tn} duplicate columns")
        if not t["pk"]:ddl_errors.append(f"{tn} missing primary key")
        for c in t["pk"]:
            if c not in t["columns"]:ddl_errors.append(f"{tn} PK missing column {c}")
            elif t["columns"][c]["nullable"]:ddl_errors.append(f"{tn}.{c} PK nullable")
    cn=[x for t in tables.values() for x in t["constraint_names"]]+[f["name"] for f in fks]
    for n,c in Counter(cn).items():
        if c>1:ddl_errors.append(f"duplicate constraint {n}")
    rels=[(f["child_table"],f["child_column"],f["parent_table"],f["parent_column"]) for f in fks]
    for r,c in Counter(rels).items():
        if c>1:ddl_errors.append(f"duplicate FK relation {r}")
    # FK validity and type
    for f in fks:
        if f["child_table"] not in tables or f["parent_table"] not in tables:
            ddl_errors.append(f"{f['name']} missing table");continue
        ct,pt=tables[f["child_table"]],tables[f["parent_table"]]
        if f["child_column"] not in ct["columns"] or f["parent_column"] not in pt["columns"]:
            ddl_errors.append(f"{f['name']} missing column");continue
        if ct["columns"][f["child_column"]]["type"]!=pt["columns"][f["parent_column"]]["type"]:
            ddl_errors.append(f"{f['name']} type mismatch")
        candidate=[pt["pk"]]+pt["uniques"]
        if not any(f["parent_column"] in u and len(u)==1 for u in candidate):
            ddl_errors.append(f"{f['name']} target not single-column PK/UNIQUE")
    # check defaults belong to CHECK enum
    for tn,t in tables.items():
        for c in t["checks"]:
            m=re.search(r"([A-Za-z0-9_]+)\s+IN\s*\((.*?)\)",c["expression"],re.I)
            if not m:continue
            col=m.group(1); vals=[x.strip().strip("'") for x in m.group(2).split(",")]
            default=t["columns"].get(col,{}).get("default")
            if default is not None:
                default=str(default).strip("'")
                if default not in vals:ddl_errors.append(f"{tn}.{col} default {default} outside enum")
    # targeted checks
    cr=tables.get("atp_credential_revision",{})
    if cr.get("pk")!=["credential_revision_id"]:ddl_errors.append("credential_revision PK wrong")
    if ["test_account_id","revision_no"] not in cr.get("uniques",[]):ddl_errors.append("credential_revision unique wrong")
    pc=tables.get("atp_permission_code",{})
    if "role_id" in pc.get("columns",{}):ddl_errors.append("permission_code contains role_id")
    rt=tables.get("atp_run_task",{})
    if str(rt.get("columns",{}).get("final_result",{}).get("default")).strip("'")!="UNKNOWN":ddl_errors.append("run_task final_result default wrong")
    ep=tables.get("atp_technical_alert_endpoint",{})
    if ep.get("pk")!=["technical_alert_endpoint_id"]:ddl_errors.append("endpoint PK wrong")
    batch=tables.get("atp_technical_alert_ingestion_batch",{})
    if ["technical_alert_endpoint_id","batch_key"] not in batch.get("uniques",[]):ddl_errors.append("batch unique key wrong")
    if any(f["child_table"]=="atp_technical_alert_ingestion_batch" and f["child_column"]=="signature_config_ref" for f in fks):
        ddl_errors.append("signature_config_ref incorrectly used as FK")
    puc=tables.get("atp_platform_user_credential",{})
    if puc.get("pk") != ["credential_id"]: ddl_errors.append("platform credential PK wrong")
    if ["user_id"] not in puc.get("uniques",[]): ddl_errors.append("platform credential user unique missing")
    if "password_hash" not in puc.get("columns",{}): ddl_errors.append("platform credential password hash missing")
    ars=tables.get("atp_auth_refresh_session",{})
    if ars.get("pk") != ["session_id"]: ddl_errors.append("auth refresh session PK wrong")
    if ["token_hash"] not in ars.get("uniques",[]): ddl_errors.append("auth refresh token hash unique missing")
    asa=tables.get("atp_auth_security_audit",{})
    if asa.get("pk") != ["audit_id"]: ddl_errors.append("auth security audit PK wrong")
    for required in ["action","operation_id","result_code","correlation_id","occurred_at","source_context_hash"]:
        if required not in asa.get("columns",{}): ddl_errors.append(f"auth security audit missing {required}")
    asr=tables.get("atp_auth_source_rate_limit",{})
    if asr.get("pk") != ["source_key_hash", "operation_id", "window_started_at"]:
        ddl_errors.append("auth source rate limit PK wrong")
    for required in ["request_count", "expires_at", "row_version"]:
        if required not in asr.get("columns", {}): ddl_errors.append(f"auth source rate limit missing {required}")
    if "ALTER COLUMN contract_version SET DEFAULT 2" not in sql:
        ddl_errors.append("V7 idempotency contract_version final default is not 2")
    if len(fks) != current_facts["database"]["foreign_key_count"]: ddl_errors.append(f"foreign keys={len(fks)}; derived={current_facts["database"]["foreign_key_count"]}")
    # schema cross-check
    sch=v.yaml("编码权威事实/DATABASE_DDL/database-schema.yaml")
    schema_tables={t["table_name"]:t for t in sch["tables"]}
    if len(schema_tables)!=current_facts["database"]["table_count"]:ddl_errors.append(f"schema tables={len(schema_tables)}")
    if set(schema_tables)!=set(tables):ddl_errors.append("schema/DDL table names differ")
    for tn,t in tables.items():
        st=schema_tables.get(tn)
        if not st: continue
        scols={c["name"]:c for c in st["columns"]}
        if set(scols)!=set(t["columns"]):ddl_errors.append(f"{tn} schema columns differ")
        if st.get("primary_key")!=t["pk"]:ddl_errors.append(f"{tn} schema PK differs")
    v.metrics.update({"ddl_tables":len(tables),"ddl_foreign_keys":len(fks)})
    v.add("DDL_STATIC_AND_SCHEMA",not ddl_errors,f"tables={len(tables)}, fks={len(fks)}",ddl_errors[:150])

    # 6 mapping identity
    with (args.root/"编码权威事实/DATABASE_DDL/object-table-mapping.csv").open(encoding="utf-8-sig",newline="") as f:
        mappings={r["object_id"]:r for r in csv.DictReader(f)}
    map_errors=[]
    for oid,(pk,_) in expected.items():
        if mappings.get(oid,{}).get("primary_key")!=pk:map_errors.append(f"{oid} mapping PK")
    v.add("OBJECT_TABLE_IDENTITY_MAPPING",not map_errors,"target identities aligned",map_errors)

    # 7 RBAC
    perm=v.yaml("编码权威事实/PERMISSION_CLOSURE/permission-closure.yaml")
    perms=perm["permission_catalog"]; roles=perm["role_templates"]; maps=perm["role_permission_mappings"]
    rbac_errors=[]
    expected_counts=(len(perms),len(roles),len(maps))
    actual=expected_counts
    derived_counts=(current_facts["rbac"]["permission_count"], current_facts["rbac"]["role_count"], current_facts["rbac"]["mapping_count"])
    if actual!=derived_counts:rbac_errors.append(f"RBAC definitions differ from derived facts: {actual} != {derived_counts}")
    pcodes={p["permission_code"] for p in perms}; rids={r["role_id"] for r in roles}
    for m in maps:
        if m["permission_code"] not in pcodes or m["role_id"] not in rids:rbac_errors.append("orphan mapping")
    sg=[m for m in maps if m["role_id"]=="ROLE-SUPER-ADMIN" and m["permission_code"]=="CROSS_PROJECT_AUTHORIZATION_GRANT_ALL"]
    if len(sg)!=1 or sg[0].get("decision")!="ALLOWED":rbac_errors.append("SUPER_ADMIN grant-all not ALLOWED")
    # CSV count
    with (args.root/"编码权威事实/PERMISSION_CLOSURE/role-permission-matrix.csv").open(encoding="utf-8-sig",newline="") as f:
        csv_maps=list(csv.DictReader(f))
    if len(csv_maps)!=len(maps):rbac_errors.append(f"role matrix CSV={len(csv_maps)} expected={len(maps)}")
    seed=(args.root/"编码权威事实/DATABASE_DDL/V4__rbac_seed_data.sql").read_text(encoding="utf-8")
    p_ins=len(re.findall(r"INSERT INTO atp_permission_code\s*\(",seed,re.I))
    r_ins=len(re.findall(r"INSERT INTO atp_role\s*\(",seed,re.I))
    m_ins=len(re.findall(r"INSERT INTO atp_role_permission\s*\(",seed,re.I))
    if (p_ins,r_ins,m_ins)!=actual:rbac_errors.append(f"seed counts={(p_ins,r_ins,m_ins)} expected={actual}")
    if seed.upper().count("ON DUPLICATE KEY UPDATE") < sum(actual):rbac_errors.append("seed is not fully idempotent")
    v.metrics.update({"permissions":len(perms),"roles":len(roles),"role_permission_mappings":len(maps)})
    v.add("RBAC_CLOSURE_AND_SEED",not rbac_errors,f"counts={actual}; seed={(p_ins,r_ins,m_ins)}",rbac_errors)

    # 8 OpenAPI
    api=v.yaml("编码权威事实/OPENAPI/openapi.yaml")
    api_errors=[]
    if str(api.get("openapi"))!="3.1.2":api_errors.append(f"openapi={api.get('openapi')}")
    components=api.get("components",{}).get("schemas",{})
    ops=[]; opids=[]; placeholders_errors=[]
    known_methods={"get","post","put","patch","delete","options","head"}
    for path,item in api.get("paths",{}).items():
        for method,op in item.items():
            if method.lower() not in known_methods or not isinstance(op,dict):continue
            ops.append((path,method,op));opids.append(op.get("operationId"))
            placeholders=set(re.findall(r"\{([^}]+)\}",path))
            params=(item.get("parameters",[]) if isinstance(item,dict) else [])+op.get("parameters",[])
            declared={p.get("name") for p in params if isinstance(p,dict) and p.get("in")=="path"}
            if placeholders!=declared:placeholders_errors.append(f"{method.upper()} {path} path params {declared}")
            pc=op.get("x-permission-code")
            if pc and pc not in pcodes:api_errors.append(f"{op.get('operationId')} unknown permission {pc}")
            if method.lower() in {"post","put","patch","delete"} and "requestBody" not in op and method.lower()!="delete":
                api_errors.append(f"{op.get('operationId')} missing requestBody")
            if not op.get("responses"):api_errors.append(f"{op.get('operationId')} missing responses")
    if None in opids or len(opids)!=len(set(opids)):api_errors.append("operationId missing or duplicate")
    api_errors.extend(placeholders_errors)
    # refs
    all_text=(args.root/"编码权威事实/OPENAPI/openapi.yaml").read_text(encoding="utf-8")
    for ref in re.findall(r"\$ref:\s*['\"]?#/components/schemas/([^'\"\s]+)",all_text):
        if ref not in components:api_errors.append(f"missing schema ref {ref}")
    # schema examples: deterministic local required/type/enum validation without network resolution
    example_fail=[]
    def check_example(schema, example, path=""):
        if not isinstance(schema,dict): return
        if "$ref" in schema and schema["$ref"].startswith("#/components/schemas/"):
            target=components.get(schema["$ref"].split("/")[-1])
            if target is not None: check_example(target,example,path)
            return
        if "enum" in schema and example not in schema["enum"]:
            raise ValueError(f"{path} not in enum")
        typ=schema.get("type")
        allowed=typ if isinstance(typ,list) else [typ]
        if example is None and "null" in allowed:return
        if "object" in allowed or "properties" in schema:
            if not isinstance(example,dict):raise ValueError(f"{path} expected object")
            for req in schema.get("required",[]):
                if req not in example:raise ValueError(f"{path}.{req} required")
            for k,val in example.items():
                if k in schema.get("properties",{}):check_example(schema["properties"][k],val,path+"."+k)
        elif "array" in allowed:
            if not isinstance(example,list):raise ValueError(f"{path} expected array")
            for i,val in enumerate(example):check_example(schema.get("items",{}),val,f"{path}[{i}]")
        elif "string" in allowed and not isinstance(example,str):raise ValueError(f"{path} expected string")
        elif ("integer" in allowed) and (not isinstance(example,int) or isinstance(example,bool)):raise ValueError(f"{path} expected integer")
        elif ("number" in allowed) and (not isinstance(example,(int,float)) or isinstance(example,bool)):raise ValueError(f"{path} expected number")
        elif "boolean" in allowed and not isinstance(example,bool):raise ValueError(f"{path} expected boolean")
    for name,schema in components.items():
        if not isinstance(schema,dict) or not schema:api_errors.append(f"empty schema {name}");continue
        if "example" in schema:
            try: check_example(schema,schema["example"],name)
            except Exception as e: example_fail.append(f"{name}: {e}")
    api_errors.extend(example_fail[:100])
    required_auth_ops={
      "login_platform_user","refresh_platform_session","logout_platform_user",
      "get_current_user","change_current_user_password","create_user",
      "reset_user_credential","enable_user","disable_user",
      "create_user_role_binding","revoke_user_role_binding"}
    if not required_auth_ops.issubset(set(opids)):
        api_errors.append(f"missing auth operations {sorted(required_auth_ops-set(opids))}")
    required_auth_schemas={
      "LoginRequest","AuthenticationTokenResource","AuthenticationResponse","CurrentUserResource",
      "CurrentUserResponse","AuthCookieActionRequest","ChangePasswordRequest",
      "AuthenticationErrorCode","AuthenticationProblemDetails",
      "OneTimeCredentialDeliveryResource","OneTimeCredentialDeliveryResponse",
      "ResetUserCredentialRequest","UserStateCommandRequest",
      "CreateUserRoleBindingRequest","RevokeUserRoleBindingRequest",
      "UserRoleBindingResource","UserRoleBindingResponse"}
    if not required_auth_schemas.issubset(set(components)):
        api_errors.append(f"missing auth schemas {sorted(required_auth_schemas-set(components))}")
    contract_rules=api.get("x-contract-rules",{})
    if contract_rules.get("code_readiness")!=EXPECTED_CODE_READINESS:
        api_errors.append(f"x-contract-rules code_readiness={contract_rules.get('code_readiness')}")
    # targeted identity
    crs=components.get("CredentialRevisionResource",{})
    if crs.get("x-primary-key")!="credential_revision_id" or "credential_revision_id" not in crs.get("required",[]):
        api_errors.append("CredentialRevisionResource identity wrong")
    eps=components.get("TechnicalAlertEndpointResource",{})
    if eps.get("x-primary-key")!="technical_alert_endpoint_id" or "technical_alert_endpoint_id" not in eps.get("required",[]):
        api_errors.append("TechnicalAlertEndpointResource identity wrong")
    rts=components.get("RunTaskResource",{})
    if rts.get("example",{}).get("final_result")!="UNKNOWN":api_errors.append("RunTaskResource example final_result wrong")
    v.metrics.update({"openapi_paths":len(api.get("paths",{})),"openapi_operations":len(ops),"openapi_schemas":len(components),"openapi_example_fail":len(example_fail)})
    v.add("OPENAPI_3_1_2",not api_errors,f"paths={len(api.get('paths',{}))}, ops={len(ops)}, schemas={len(components)}",api_errors[:150])

    # 9 Events
    ereg=v.yaml("编码权威事实/EVENT_CONTRACTS/event-registry.yaml")
    events=ereg["events"]; event_errors=[]
    schema_dir=args.root/"编码权威事实/EVENT_CONTRACTS"
    files={p.relative_to(schema_dir).as_posix() for p in (schema_dir/"schemas").glob("*.json")}
    registered={e["schema_path"] for e in events}
    if len(events)!=len({e["event_type"] for e in events}):event_errors.append("duplicate event type")
    if registered!=files:event_errors.append(f"registry/schema mismatch missing={len(registered-files)} unlisted={len(files-registered)}")
    required_env={"event_id","event_type","event_version","occurred_at","aggregate_id","sequence","correlation_id","causation_id","project_id","payload"}
    for e in events:
        p=schema_dir/e["schema_path"]
        try:j=json.loads(p.read_text(encoding="utf-8"))
        except Exception as ex:event_errors.append(f"{e['schema_path']}: {ex}");continue
        if not required_env.issubset(set(j.get("required",[]))):event_errors.append(f"{e['event_type']} envelope")
        if not e.get("producer") or not e.get("consumers"):event_errors.append(f"{e['event_type']} producer/consumer")
        if e.get("partition_key") not in {"aggregate_id", e.get("aggregate_id_field")}:event_errors.append(f"{e['event_type']} partition/aggregate mismatch")
        payload=j.get("properties",{}).get("payload",{})
        for field in e.get("payload_identity_fields",[]):
            if field not in payload.get("required",[]):event_errors.append(f"{e['event_type']} payload missing {field}")
        if e.get("aggregate_id_field") not in e.get("payload_identity_fields",[]):event_errors.append(f"{e['event_type']} aggregate identity not payload")
    # targeted
    for e in events:
        if e["event_type"].startswith("credential_revision.") and e.get("aggregate_id_field")!="credential_revision_id":
            event_errors.append(f"{e['event_type']} wrong identity")
        if e["event_type"].startswith("technical_alert_endpoint.") and e.get("aggregate_id_field")!="technical_alert_endpoint_id":
            event_errors.append(f"{e['event_type']} wrong identity")
    v.metrics.update({"events":len(events),"event_producers":len({e.get('producer') for e in events}),"event_consumer_sets":len({tuple(e.get('consumers',[])) for e in events})})
    v.add("EVENT_CONTRACTS",not event_errors,f"events={len(events)}, schemas={len(files)}",event_errors[:150])

    # 10 Acceptance and confirmed decisions
    acc=v.json("编码权威事实/ACCEPTANCE_CLOSURE/acceptance-closure.json")
    specs=acc["acceptance_closure"]; acc_errors=[]
    acc_metadata=acc.get("metadata",{})
    if acc_metadata.get("current_facts_source") != "tools/current_facts.py":
        acc_errors.append("acceptance metadata must delegate volatile counts/current catalog to tools/current_facts.py")
    allowed_statuses={"SPECIFIED","PASSED","FAILED","BLOCKED_BY_ENVIRONMENT"}
    allowed_evidence={"EXPECTED_NOT_EXECUTED","NOT_STARTED","VERIFIED","FAILED","BLOCKED_BY_ENVIRONMENT"}
    if any(a.get("status") not in allowed_statuses for a in specs):acc_errors.append("invalid acceptance status")
    if any(a.get("evidence_status") not in allowed_evidence for a in specs):acc_errors.append("invalid evidence status")
    if any((a.get("status")=="PASSED") != (a.get("evidence_status")=="VERIFIED") for a in specs):
        acc_errors.append("PASSED and VERIFIED evidence are not coherent")
    status_counts={status:sum(a.get("status")==status for a in specs) for status in allowed_statuses}
    evidence_gap_count=sum(a.get("evidence_status")!="VERIFIED" for a in specs)
    derived_acceptance=current_facts["acceptance"]
    if len(specs)!=derived_acceptance["count"] or status_counts["SPECIFIED"]!=derived_acceptance["specified_count"] or status_counts["PASSED"]!=derived_acceptance["passed_count"] or evidence_gap_count!=derived_acceptance["evidence_gap_count"]:
        acc_errors.append("acceptance derived facts mismatch")
    for a in specs:
        if not (a.get("requirement_ids") or a.get("invariant_id") or a.get("rule_id")):acc_errors.append(f"{a.get('acceptance_id')} no upstream")
        for k in ["preconditions","action","expected_response","expected_state","database_assertions","event_assertions","permission_assertions","evidence_type"]:
            if not a.get(k):acc_errors.append(f"{a.get('acceptance_id')} missing {k}")
    safety=v.yaml("数据安全、制品生命周期与验收基线/数据安全、制品生命周期与验收基线.yaml")
    def find_id(x,target):
        if isinstance(x,dict):
            if x.get("acceptance_id")==target:return x
            for vv in x.values():
                r=find_id(vv,target)
                if r:return r
        elif isinstance(x,list):
            for vv in x:
                r=find_id(vv,target)
                if r:return r
    for aid in ["ACC-00078","ACC-00079","ACC-00080","ACC-00081"]:
        a=find_id(safety,aid)
        if not a or a.get("current_scope") not in {"IN_SCOPE_APPROVED","IN_SCOPE_MANDATORY"} or a.get("completion_status")!="CURRENT_ACCEPTANCE_SPECIFICATION":
            acc_errors.append(f"{aid} not current acceptance specification")
    # Recovery center
    rolesdoc=v.yaml("用户角色、核心场景与模块菜单/用户角色、核心场景与模块菜单.yaml")
    recovery=[]
    def walk(x):
        if isinstance(x,dict):
            if x.get("name")=="统一恢复中心":recovery.append(x)
            for vv in x.values():walk(vv)
        elif isinstance(x,list):
            for vv in x:walk(vv)
    walk(rolesdoc)
    if not recovery or any(x.get("status")!="OUT_OF_SCOPE_V1" for x in recovery):acc_errors.append("recovery center status wrong")
    v.metrics.update({"acceptance":len(specs),"acceptance_passed":sum(a.get('status')=="PASSED" for a in specs)})
    passed_count=sum(a.get("status")=="PASSED" for a in specs)
    v.add("ACCEPTANCE_SPECIFICATION",not acc_errors,f"total={len(specs)}, passed={passed_count}",acc_errors[:150])

    # 11 Gate separation and Agent/Skill consistency
    gate_errors=[]
    sd=v.yaml("编码权威事实/SYSTEM_DESIGN.yaml")
    if sd["release_gate"]["authority_readiness"]["status"]!=EXPECTED_CODE_READINESS:gate_errors.append("SYSTEM_DESIGN code gate")
    if "REAL_ACCEPTANCE_EVIDENCE" not in sd["release_gate"]["authority_readiness"].get("does_not_require",[]):gate_errors.append("real acceptance still code blocker")
    if sd.get("runtime_gate_contract", {}).get("implementation_status") not in {
        "IMPLEMENTATION_PENDING_FOR_GOV_P1_002_003_005",
        "IMPLEMENTED_PENDING_RUNTIME_VALIDATION",
        "IMPLEMENTED_RUNTIME_VALIDATED",
    }:
        gate_errors.append("implementation gate")
    if sd.get("release_gate", {}).get("implementation_release_readiness", {}).get("status_source") != "SYSTEM_DESIGN.runtime_gate_contract.implementation_status":
        gate_errors.append("implementation status must be referenced from runtime_gate_contract")
    database_configuration=sd["database_contract"].get("connection_configuration",{})
    if database_configuration.get("application_database_url_env")!="ATP_DATABASE_URL":gate_errors.append("application database URL governance")
    if database_configuration.get("mysql_admin_url_env")!="ATP_MYSQL_ADMIN_URL":gate_errors.append("MySQL admin URL governance")
    auth_runtime_evidence=sd["database_contract"].get("authentication_runtime_evidence",{})
    if auth_runtime_evidence.get("mysql",{}).get("status_name")!="AUTH_MYSQL_RUNTIME_GATE":gate_errors.append("auth MySQL runtime Gate naming")
    if auth_runtime_evidence.get("browser",{}).get("status_name")!="AUTH_BROWSER_RUNTIME_GATE":gate_errors.append("auth browser runtime Gate naming")
    repo_root=args.root.parents[1]
    runtime_docs=[
      (repo_root/"AGENTS.md", [AUTHORITY_MODEL, "docs/authority", "MUST_NOT_INVOKE_GIT", EXPECTED_CODE_READINESS]),
      (repo_root/".agents/skills/ai-auto-test-platform-core/SKILL.md", [AUTHORITY_MODEL, "docs/authority", EXPECTED_CODE_READINESS]),
    ]
    for path,tokens in runtime_docs:
        if not path.exists():
            gate_errors.append(f"missing runtime governance {path.relative_to(repo_root)}")
            continue
        text=path.read_text(encoding="utf-8")
        for token in tokens:
            if token not in text:gate_errors.append(f"{path.relative_to(repo_root)} missing {token}")
    v.add("AGENTS_SKILL_GATE_CONSISTENCY",not gate_errors,"living authority and implementation gate model aligned",gate_errors)

    report={
      "authority_model":AUTHORITY_MODEL,
      "authority_root":"docs/authority",
      "executed_at":__import__("time").strftime("%Y-%m-%dT%H:%M:%SZ",__import__("time").gmtime()),
      "validator":"validate_all.py",
      "python":sys.version,
      "status":"PASS" if not v.errors else "FAIL",
      "metrics":v.metrics,
      "checks":v.checks,
      "error_count":len(v.errors),
      "errors":v.errors,
    }
    raw=json.dumps(report,ensure_ascii=False,indent=2)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(raw,encoding="utf-8")
    print(raw)
    return 0 if not v.errors else 1

if __name__=="__main__":
    raise SystemExit(main())
