# How I use OpenMy to keep daily context under control

This is not a hello-world walkthrough.

It is a practical day-to-day loop that you can actually reuse.

## Morning

1. Put yesterday's and today's recordings into one stable folder.
2. Run `openmy quick-start`.
3. Read the daily briefing first so you can see what really moved and what is still stuck.

## During the day

1. Keep dropping new recordings into the same folder.
2. When needed, run `openmy run 2026-04-13 --audio path/to/file.wav`.
3. If a name or role is wrong, fix it immediately with `openmy correct`.

## Evening

1. Run `openmy context --compact` to see whether the cross-day context changed.
2. Run `openmy query --kind open --query project-name` to find unfinished work.
3. Open the local web report and scan the briefing, scenes, and charts.

## What this solves

- You do not have to reconstruct your day from memory.
- You do not have to dig through chats and recordings to find evidence.
- Your agent does not have to ask from zero every time.

## Smallest command set

```bash
openmy quick-start
openmy context --compact
openmy query --kind open --query OpenMy
```
