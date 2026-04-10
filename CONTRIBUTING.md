# Contributing to OpenMy

感谢你对 OpenMy 的关注！

## 开发环境

```bash
git clone https://github.com/openmy-ai/openmy.git
cd openmy
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## 运行测试

```bash
python3 -m pytest tests/ -v
```

测试不依赖真实 API key，在没有 `GEMINI_API_KEY` 的环境也能全绿。

## 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/)：

- `feat:` 新功能
- `fix:` 修 bug
- `refactor:` 重构（不改行为）
- `docs:` 文档
- `test:` 测试
- `chore:` 杂项

## PR 流程

1. Fork → 新分支
2. 改代码 + 补测试
3. `pytest tests/` 全绿
4. 提 PR，描述清楚改了什么、为什么

## 代码风格

- Python 3.10+
- 变量名用英文，注释和用户可见文案用中文
- 每个 service 模块独立，不跨模块直接 import 内部函数

## 有问题？

开 Issue 或直接在 PR 里讨论。
