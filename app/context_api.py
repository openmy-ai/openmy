from __future__ import annotations


def _server():
    import app.server as server_module
    return server_module


def load_active_context_model():
    server = _server()
    from openmy.services.context.active_context import ActiveContext

    ctx_path = server.DATA_ROOT / 'active_context.json'
    if not ctx_path.exists():
        return None
    return ActiveContext.load(ctx_path)


def refresh_active_context_snapshot() -> dict:
    server = _server()
    from openmy.services.context.consolidation import consolidate
    from openmy.services.context.corrections import apply_corrections, load_corrections

    ctx_path = server.DATA_ROOT / 'active_context.json'
    corrections = load_corrections(server.DATA_ROOT)
    existing = load_active_context_model()

    if existing is not None:
        ctx = apply_corrections(existing, corrections) if corrections else existing
    else:
        ctx = consolidate(server.DATA_ROOT)

    ctx.save(ctx_path)
    return ctx.to_dict()


def _append_context_correction(op: str, target_type: str, target_id: str, payload: dict | None = None, reason: str = '') -> None:
    server = _server()
    from openmy.services.context.corrections import append_correction, create_correction_event

    event = create_correction_event(actor='user', op=op, target_type=target_type, target_id=target_id, payload=payload, reason=reason)
    append_correction(server.DATA_ROOT, event)


def handle_close_loop(data: dict) -> dict:
    server = _server()
    query = str(data.get('query', '')).strip()
    status = str(data.get('status', 'done')).strip() or 'done'
    ctx = load_active_context_model()
    if ctx is None:
        return {'success': False, 'error': 'active_context.json 不存在，请先生成 context。'}
    loop = server._resolve_item(ctx.rolling_context.open_loops, query, lambda item: [item.loop_id, item.id, item.title])
    if loop is None:
        return {'success': False, 'error': f'没找到待办：{query}'}
    target_id = loop.loop_id or loop.id or loop.title
    _append_context_correction('close_loop', 'loop', target_id, {'status': status, 'target_title': loop.title}, str(data.get('reason', '')).strip())
    return {'success': True, 'target_id': target_id, 'context': refresh_active_context_snapshot()}


def handle_reject_loop(data: dict) -> dict:
    server = _server()
    query = str(data.get('query', '')).strip()
    ctx = load_active_context_model()
    if ctx is None:
        return {'success': False, 'error': 'active_context.json 不存在，请先生成 context。'}
    loop = server._resolve_item(ctx.rolling_context.open_loops, query, lambda item: [item.loop_id, item.id, item.title])
    if loop is None:
        return {'success': False, 'error': f'没找到待办：{query}'}
    target_id = loop.loop_id or loop.id or loop.title
    _append_context_correction('reject_loop', 'loop', target_id, {'target_title': loop.title}, str(data.get('reason', '')).strip())
    return {'success': True, 'target_id': target_id, 'context': refresh_active_context_snapshot()}


def handle_merge_project(data: dict) -> dict:
    server = _server()
    source_query = str(data.get('source', '')).strip()
    target_query = str(data.get('target', '')).strip()
    ctx = load_active_context_model()
    if ctx is None:
        return {'success': False, 'error': 'active_context.json 不存在，请先生成 context。'}
    source_project = server._resolve_item(ctx.rolling_context.active_projects, source_query, lambda item: [item.project_id, item.id, item.title])
    target_project = server._resolve_item(ctx.rolling_context.active_projects, target_query, lambda item: [item.project_id, item.id, item.title])
    if source_project is None or target_project is None:
        return {'success': False, 'error': '找不到要合并的项目。'}
    source_id = source_project.project_id or source_project.id or source_project.title
    target_id = target_project.project_id or target_project.id or target_project.title
    _append_context_correction('merge_project', 'project', source_id, {'target_title': source_project.title, 'merge_into': target_id, 'merge_into_title': target_project.title}, str(data.get('reason', '')).strip())
    return {'success': True, 'target_id': source_id, 'context': refresh_active_context_snapshot()}


def handle_reject_project(data: dict) -> dict:
    server = _server()
    query = str(data.get('query', '')).strip()
    ctx = load_active_context_model()
    if ctx is None:
        return {'success': False, 'error': 'active_context.json 不存在，请先生成 context。'}
    project = server._resolve_item(ctx.rolling_context.active_projects, query, lambda item: [item.project_id, item.id, item.title])
    if project is None:
        return {'success': False, 'error': f'没找到项目：{query}'}
    target_id = project.project_id or project.id or project.title
    _append_context_correction('reject_project', 'project', target_id, {'target_title': project.title}, str(data.get('reason', '')).strip())
    return {'success': True, 'target_id': target_id, 'context': refresh_active_context_snapshot()}


def handle_reject_decision(data: dict) -> dict:
    server = _server()
    query = str(data.get('query', '')).strip()
    ctx = load_active_context_model()
    if ctx is None:
        return {'success': False, 'error': 'active_context.json 不存在，请先生成 context。'}
    decision = server._resolve_item(ctx.rolling_context.recent_decisions, query, lambda item: [item.decision_id, item.id, item.decision, item.topic])
    if decision is None:
        return {'success': False, 'error': f'没找到决策：{query}'}
    target_id = decision.decision_id or decision.id or decision.decision
    _append_context_correction('reject_decision', 'decision', target_id, {'target_title': decision.decision}, str(data.get('reason', '')).strip())
    return {'success': True, 'target_id': target_id, 'context': refresh_active_context_snapshot()}
