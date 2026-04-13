# 我每天怎么用 OpenMy 收上下文

这不是 hello world。

这是一个能真的跑起来的日常流程：

## 早上

1. 我先把昨天和今天的录音都放进固定文件夹。
2. 跑一次 `openmy quick-start`。
3. 先看日报，确认昨天到底推进了什么、卡在哪。

## 白天

1. 有新录音就继续丢进同一个文件夹。
2. 需要时再跑一次 `openmy run 2026-04-13 --audio path/to/file.wav`。
3. 如果名字识别错了，马上用 `openmy correct` 修掉，不等以后。

## 晚上

1. 跑 `openmy context --compact` 看跨天上下文有没有更新。
2. 跑 `openmy query --kind open --query 项目名` 查还有哪些待办没收完。
3. 打开本地网页，把当天的日报、场景和图表扫一遍。

## 这套流程解决了什么问题

- 不用靠脑子回忆今天到底做了什么。
- 不用翻聊天记录和录音文件找证据。
- 不用每次都重新告诉 Agent 最近在推进什么。

## 最小命令清单

```bash
openmy quick-start
openmy context --compact
openmy query --kind open --query OpenMy
```

## 什么时候最值

- 你白天说了很多话，晚上已经想不起来细节。
- 你同时推好几个项目，切换很频繁。
- 你已经在重度使用 Agent，希望它别老从头问。
