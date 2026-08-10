# Python / FastAPI Quality Rules

- Route只负责HTTP适配，不直接承载核心业务流程或SQL。
- Application/Domain方法保持单一业务目的；复杂状态转换应有原因型中文注释或Docstring。
- Repository查询不得把SQLAlchemy持久化细节泄漏给领域层。
- 不吞异常；转换异常时保留可定位上下文和统一错误语义。
- 同一业务不变量不得在多个Service各自实现一套。
- 明显循环SQL/N+1、无界重试或重复解析固定契约属于质量风险。
- 公共能力在签名不足以表达副作用/状态影响时提供简短Docstring。
