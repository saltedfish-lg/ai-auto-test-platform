-- Living Authority governance migration: retire the obsolete platform-design-baseline-release runtime model.
-- Historical V3 DDL remains immutable evidence; current schema no longer exposes this governance object.
DROP TABLE IF EXISTS atp_platform_design_baseline_release;
