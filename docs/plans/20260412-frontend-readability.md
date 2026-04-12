# OpenMy 前端可读性修改文档

## 当前问题总结

### 🔴 P0：详细记录的 "事件" 标签冗余
**位置**：`app/static/app.js` → `getSegmentDistillation()` (第 738-755 行)

当一个时间段有 meta 信息（events/decisions/todos）时，渲染逻辑是：
```
preview（摘要文字）
事件 和伴侣讨论周末杭州行程    ← 这行多余
```
`<strong>事件</strong>` 这个标签+摘要跟上面的 preview 内容几乎一样，纯重复。

**修法**：当 preview 摘要已存在时，不再重复渲染 highlights 里的同义内容。或者直接隐藏 highlights 区块（因为上面的四色面板已经展示了这些信息）。

```javascript
// 文件：app/static/app.js 第 738-755 行
// 修改 getSegmentDistillation()

// 修改前：
function getSegmentDistillation(segment, meta) {
  const highlights = [];
  // ... 遍历 events/decisions/todos 生成 highlights
  if (highlights.length > 0) {
    return `${preview ? `<div>${preview}</div>` : ''}<div class="muted"...>${highlights.join('<br>')}</div>`;
  }
  // ...
}

// 修改后：只显示 preview 摘要，不再重复列 highlights
function getSegmentDistillation(segment, meta) {
  // 直接返回 summary/preview，不再拼接 highlights
  if (segment.summary) return escapeHtml(plainText(segment.summary));
  return escapeHtml(plainText(segment.preview || segment.text || '').slice(0, 200));
}
```

---

### 🔴 P0：摘要文字被截断 + `---` 泄露
**位置**：`app/static/app.js` → `getSegmentDistillation()` 和 `fmtText()`

摘要末尾出现 `---`（Markdown 分隔符）和句子中断，原因是：
1. `segment.summary` 或 `segment.preview` 里包含原始 Markdown 的 `---`
2. 没有清理这些标记

**修法**：在 `plainText()` 函数里清理 `---`

```javascript
// 文件：app/static/app.js 第 71-78 行
// 修改 plainText()

// 修改前：
function plainText(value) {
  return String(value || '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/<[^>]+>/g, '')
    .trim();
}

// 修改后：加上 --- 和多余换行的清理
function plainText(value) {
  return String(value || '')
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/<[^>]+>/g, '')
    .replace(/^---+$/gm, '')      // 清理 Markdown 分隔线
    .replace(/\n{3,}/g, '\n\n')   // 合并多余空行
    .trim();
}
```

---

### 🟡 P1：首页摘要截断太短
**位置**：`app/static/app.js` → `truncateSummary()` (第 238-242 行)

```javascript
function truncateSummary(text, maxLength = 20) {
```
默认 **20 个字就截断**，太短了。"伴侣，今天晚上吃火锅。然后把 Open..." 就被切了。

**修法**：改成 40-60 字

```javascript
function truncateSummary(text, maxLength = 50) {
```

---

### 🟡 P1：详细记录所有信息重复展示
**位置**：`app/static/app.js` → `renderDayLayout()` (第 658-706 行)

页面结构是：
1. 顶部摘要（summary-callout）
2. 四色面板（发生了什么 / 打算做什么 / 记住了什么 / 决定了什么）
3. **详细记录** ← 几乎重复了上面的内容
4. 数据图表

用户看完四色面板已经知道了所有信息，详细记录默认展开就是在看第二遍。

**修法**：详细记录区域默认折叠，加一个展开按钮

```javascript
// 文件：app/static/app.js 第 678-695 行
// 修改 renderDayLayout() 里的详细记录区域

// 修改前：
<section class="article-section">
  <h2>详细记录</h2>
  <div class="record-list">
    ${detail.segments.map(...).join('')}
  </div>
</section>

// 修改后：默认折叠
<section class="article-section">
  <h2 class="collapsible-header" onclick="toggleSection(this)">
    详细记录 <span class="collapse-arrow">▶</span>
  </h2>
  <div class="record-list" style="display:none">
    ${detail.segments.map(...).join('')}
  </div>
</section>
```

在 app.js 末尾加：
```javascript
function toggleSection(header) {
  const content = header.nextElementSibling;
  const arrow = header.querySelector('.collapse-arrow');
  if (content.style.display === 'none') {
    content.style.display = '';
    arrow.textContent = '▼';
  } else {
    content.style.display = 'none';
    arrow.textContent = '▶';
  }
}
```

---

### 🟡 P1：四色面板的标签太"工程化"
**位置**：`app/static/app.js` → `renderMetaPanels()` (第 708-736 行)

```javascript
const groups = [
  { key: 'events', title: '发生了什么', dot: '#2eaadc' },
  { key: 'intents', title: '打算做什么', dot: '#0f7b6c' },
  { key: 'facts', title: '记住了什么', dot: '#64748b' },
  { key: 'decisions', title: '决定了什么', dot: '#d9730d' },
];
```

这四个标题还行，但面板内每条 item 的格式是：
```
14:00   和伴侣讨论周末杭州行程
```
这里的 `14:00` 用 `time-tag` 样式比较小，但如果有 `project` 标签会变得拥挤。

**修法**：保持现有结构，但去掉 project-tag（项目标签），改成在摘要后面用括号标注

```javascript
// 修改前：
${project ? `<span class="project-tag">${project}</span>` : ''}
${summary}

// 修改后：
${summary}${project ? ` (${project})` : ''}
```

---

### 🟢 P2：`2099-12-31` 测试数据暴露在侧边栏
**位置**：数据层问题

侧边栏出现了 `2099-12-31` 这个日期，看起来是测试数据。

**修法**：在 `renderSidebar()` 里过滤掉不合理日期（比如超过当前年份+1）

```javascript
// 在 renderSidebar() 第 413 行附近
const currentYear = new Date().getFullYear();
const validDates = state.allDates.filter(item => {
  const year = parseInt(item.date.split('-')[0]);
  return year <= currentYear + 1;
});
```

---

## 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| `app/static/app.js` | `plainText()` 清理 `---` |
| `app/static/app.js` | `truncateSummary()` maxLength 20→50 |
| `app/static/app.js` | `getSegmentDistillation()` 去掉重复 highlights |
| `app/static/app.js` | `renderDayLayout()` 详细记录默认折叠 |
| `app/static/app.js` | `renderMetaPanels()` project 标签改括号 |
| `app/static/app.js` | `renderSidebar()` 过滤测试日期 |
| `app/static/style.css` | 加 `.collapsible-header` 样式 |

## 验证

1. 刷新 `http://localhost:8420/`，检查首页摘要不再被 20 字截断
2. 点进任意日期，确认：
   - 四色面板清晰完整
   - 没有重复的"事件"标签
   - 摘要没有 `---`
   - 详细记录默认折叠
3. 侧边栏没有 `2099-12-31`
4. 测试 `ruff check .` 和 `python3 -m pytest tests/ -q`
