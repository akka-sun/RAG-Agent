# 阶段 1：FastAPI 与 PostgreSQL 设计

日期：2026-07-18

## 1. 目标

阶段 1 建立从 HTTP 请求到 PostgreSQL 事务提交的完整链路，实现知识库创建、列表、详情和删除，并通过统一错误响应、Alembic 迁移、单元测试和真实数据库集成测试验证设计。

本阶段的学习目标是能够解释请求校验、依赖注入、事务、连接池、外键、索引以及 API、Service、Repository 和 ORM 各层的职责边界。

## 2. 范围

本阶段实现：

- PostgreSQL Docker Compose 服务与健康检查。
- SQLAlchemy 2.x 异步 Engine、Session 工厂和请求级会话依赖。
- Alembic 异步迁移环境和 `knowledge_bases` 首个迁移。
- 知识库创建、列表、详情和删除接口。
- Repository 与 Service 分层。
- 统一的 API 错误响应。
- 不访问数据库的单元测试和访问真实 PostgreSQL 的集成测试。
- 空数据库迁移、Ruff、Pyright、pytest 和真实 HTTP 验收。

本阶段不实现：

- 文档、摄取任务、会话、消息和引用表。
- Redis、ARQ、MinIO、Milvus、模型客户端和解析器。
- 登录、权限、多租户、分页、搜索、批量操作和软删除。
- 为未来模块预设通用插件、通用基类或复杂领域框架。

## 3. 实施方式

采用“基础设施建立一次，知识库用例按纵向切片交付”的方式：

1. 先建立 PostgreSQL、异步 SQLAlchemy 和 Alembic，使空库可以迁移。
2. 再建立 KnowledgeBase 模型及 Repository 数据访问接口。
3. 按创建、列表与详情、删除的顺序贯通 API、Service 和 Repository。
4. 最后补齐统一错误响应、集成测试和阶段验收文档。

每个切片遵循测试驱动开发：先观察目标测试因缺少行为而失败，再实现最小代码使其通过。每个任务形成独立、可审查、可回退的提交。

## 4. 模块与文件边界

阶段结束时新增或扩展以下模块：

- `app/config.py`：PostgreSQL 连接配置的唯一入口。
- `app/db.py`：创建异步 Engine、Session 工厂和 FastAPI 会话依赖。
- `app/models/base.py`：声明式 ORM Base 与公共命名约定。
- `app/models/knowledge_base.py`：KnowledgeBase ORM 模型。
- `app/schemas/knowledge_base.py`：请求与响应模型。
- `app/repositories/knowledge_base.py`：知识库 SQLAlchemy 查询与持久化。
- `app/services/knowledge_base.py`：知识库业务用例和业务异常。
- `app/api/dependencies.py`：Repository/Service 的依赖装配。
- `app/api/errors.py`：业务异常到统一 HTTP 错误的映射。
- `app/api/routes/knowledge_bases.py`：知识库 HTTP 路由与响应装配。
- `app/main.py`：注册错误处理器和知识库路由，不直接执行 ORM 查询。
- `alembic/` 与 `alembic.ini`：数据库迁移环境和版本脚本。
- `tests/unit/`：Service、错误映射和路由的隔离测试。
- `tests/integration/`：真实 PostgreSQL Repository、迁移和 HTTP 数据库链路测试。

不引入通用 Repository 基类。当前只有一个聚合，显式实现更容易理解事务和查询行为；出现真实重复后再提取抽象。

## 5. 数据模型

`knowledge_bases` 表包含：

| 字段 | 类型 | 约束 | 含义 |
|---|---|---|---|
| `id` | UUID | 主键 | 知识库稳定标识 |
| `name` | VARCHAR(200) | 非空、唯一 | 本地单用户范围内唯一名称 |
| `description` | TEXT | 非空、默认空字符串 | 知识库说明 |
| `embedding_model` | VARCHAR(200) | 非空 | 固定的 Embedding 模型名称 |
| `embedding_dimension` | INTEGER | 非空、大于 0 | 固定向量维度 |
| `created_at` | TIMESTAMPTZ | 非空 | 创建时间 |
| `updated_at` | TIMESTAMPTZ | 非空 | 最近更新时间 |

业务不允许修改 Embedding 模型与维度。本阶段不提供更新接口，避免在知识库已有数据后产生向量维度不一致。名称唯一性由数据库唯一约束兜底，Service 将唯一约束冲突转换为稳定的业务错误。

数据库时间统一使用 UTC，API 以带时区的 ISO 8601 字符串输出。

## 6. API 契约

所有路径使用现有 `/api/v1` 前缀。

### 6.1 创建知识库

- `POST /api/v1/knowledge-bases`
- 请求：`name`、`description`、`embedding_model`、`embedding_dimension`
- 成功：`201 Created`，返回完整知识库响应。
- 名称冲突：`409 Conflict`。
- 请求字段无效：`422 Unprocessable Entity`，转换为统一错误结构。

### 6.2 知识库列表

- `GET /api/v1/knowledge-bases`
- 成功：`200 OK`，返回数组。
- 顺序：按 `created_at` 升序，再按 `id` 升序，保证确定性。
- 本阶段不分页；数据量边界由本地学习项目范围保证。

### 6.3 知识库详情

- `GET /api/v1/knowledge-bases/{knowledge_base_id}`
- 成功：`200 OK`。
- ID 格式错误：`422 Unprocessable Entity`。
- 资源不存在：`404 Not Found`。

### 6.4 删除知识库

- `DELETE /api/v1/knowledge-bases/{knowledge_base_id}`
- 成功：`204 No Content`。
- 资源不存在：`404 Not Found`。

总体设计要求非空知识库禁止删除。阶段 1 尚无 documents 表，因此删除服务保留明确的“可删除性检查”边界，但当前实现只需处理存在性；真正的非空判断在文档模型加入时通过测试驱动扩展，不伪造尚不存在的数据关系。

## 7. 统一错误响应

非成功响应统一为：

```json
{
  "error": {
    "code": "knowledge_base_not_found",
    "message": "知识库不存在",
    "details": null
  }
}
```

- `code`：稳定、可供程序判断的英文标识。
- `message`：面向当前中文 API 使用者的说明。
- `details`：可选结构化细节；没有细节时为 `null`。

阶段 1 至少定义：

- `validation_error` → 422。
- `knowledge_base_not_found` → 404。
- `knowledge_base_name_conflict` → 409。
- `internal_error` → 500，响应不得暴露 SQL、连接串或 traceback。

日志保留原始异常用于调试；API 只返回稳定契约。

## 8. 事务与数据流

创建知识库的数据流：

```text
HTTP 请求
→ Pydantic 请求校验
→ FastAPI 注入 AsyncSession
→ 注入 KnowledgeBaseRepository
→ KnowledgeBaseService 执行业务用例
→ Repository add/flush
→ Service 决定提交
→ Repository refresh/查询结果
→ API 转换响应
```

事务边界属于 Service 用例。Repository 负责查询、`add`、`flush` 和删除，不自行 `commit`；这样一个 Service 将来可以在同一事务中协调多个 Repository。请求失败时会话依赖负责回滚并关闭 Session。

读取用例不提交事务。创建和删除成功后提交；提交失败时回滚并向上抛出，由错误层转换为安全的 500 响应。唯一约束冲突被识别为名称冲突并返回 409。

连接池由 SQLAlchemy AsyncEngine 管理。应用代码不手动保存全局 Session；每个请求获取独立 Session。

## 9. PostgreSQL 与迁移

Compose 新增 `postgres` 服务：

- 使用固定主版本的官方 PostgreSQL 镜像。
- 数据保存在命名卷中。
- 仅绑定宿主机 `127.0.0.1`，不向局域网公开。
- 使用 `pg_isready` 健康检查。
- `api` 在 PostgreSQL healthy 后启动。

API 容器通过 Compose 服务名 `postgres` 连接数据库，不使用 `localhost`。测试使用独立测试数据库，不能清空或复用开发数据库。

Alembic 使用与应用相同的模型元数据和数据库 URL。验收必须证明：从空数据库执行 `alembic upgrade head` 后可以运行集成测试；迁移脚本不得依赖应用启动时自动建表。

## 10. 测试策略

### 10.1 单元测试

- 配置字符串能生成正确的异步数据库 URL。
- Service 创建、查询、列表、删除的正常与异常路径。
- Repository 使用协议或确定性替身，单元测试不访问 PostgreSQL。
- 业务异常映射到正确状态码和统一错误结构。
- 路由使用依赖覆盖，不启动真实数据库。

### 10.2 集成测试

- Alembic 能从空测试数据库升级到 head。
- Repository 在真实 PostgreSQL 中正确创建、读取、排序和删除。
- 唯一名称约束真实生效。
- API 请求通过真实 AsyncSession 完成提交和回读。
- 每个测试隔离数据；失败测试不能污染后续测试。

### 10.3 质量门槛

- `ruff format --check app tests` 通过。
- `ruff check app tests` 通过。
- `pyright` 输出 0 errors。
- 单元测试全部通过。
- PostgreSQL 集成测试全部通过。
- 空库迁移成功。
- 真实 HTTP 完成创建、列表、详情和删除链路。
- 默认测试不访问任何付费或不稳定外部服务。

## 11. 失败处理与安全边界

- 数据库不可用时知识库业务请求返回安全的 500 错误；现有 live 检查仍只反映 API 进程存活。本阶段不新增 ready 接口。
- 数据库连接串来自环境变量，不提交真实密码；`.env.example` 只保存本地示例值。
- 请求日志和错误响应不得输出数据库密码。
- 名称冲突不能依赖“先查再写”保证正确性；数据库唯一约束是并发下的最终保证。
- 删除不存在的知识库返回 404，不伪装成功。
- 本阶段不自动重试写事务，避免掩盖未知的提交结果。

## 12. 阶段验收

学习者需要能够：

1. 从路由逐层解释到 PostgreSQL 提交和响应返回。
2. 解释路由为什么不直接执行 ORM 查询。
3. 解释 `flush`、`commit`、`rollback` 和 `refresh` 的区别。
4. 解释连接池与请求级 Session 的关系。
5. 从空数据库执行迁移并运行集成测试。
6. 说明数据库唯一约束为何仍是名称冲突的最终保证。
7. 说明单元测试与真实 PostgreSQL 集成测试分别发现什么问题。

完成阶段验收后，更新 `README.md` 和 `docs/learning-roadmap.md`，再进入阶段 2 的最小离线 RAG。
