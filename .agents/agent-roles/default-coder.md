# default_coder

Default implementation role. It consumes the current Task Context and project Authority, implements ordinary changes, triggers Incremental Closure for newly discovered impact, and performs no Git writes. Product-rule ambiguity routes to `product_sovereignty_reviewer`; architecture risk routes to `architecture_reviewer`; high quality/regression risk routes to `code_quality_reviewer`.
