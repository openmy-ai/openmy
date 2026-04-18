// tokens.js — 常量和标签映射
export const PIPELINE_KIND_LABELS = {
  context: '刷新上下文',
  clean: '清理文本',
  roles: '识别对象',
  distill: '整理摘要',
  briefing: '生成日报',
  run: '重新运行',
};

export const PIPELINE_STATUS_LABELS = {
  queued: '排队中',
  running: '运行中',
  paused: '已暂停',
  succeeded: '已完成',
  partial: '已部分完成',
  cancelled: '已取消',
  interrupted: '已中断',
  failed: '失败',
};
