---
name: openmy-transcript-confirm
description: Use after distillation to confirm uncertain transcript spans with the user before they enter the daily briefing
---

# OpenMy Transcript Confirm

## Purpose

After distillation, ask the user about uncertain transcript spans (`[?词]`) that would affect the daily briefing. Confirmed corrections feed back into the personal dictionary and vocab so future transcriptions get it right.

## Trigger

Use it when:
- `distill.submit` has completed (all scene summaries saved)
- `transcript.confirm.pending` returns one or more items

Do NOT trigger if:
- Distillation is not finished yet
- `transcript.confirm.pending` returns an empty items list

## Action

- `openmy skill transcript.confirm.pending --date YYYY-MM-DD --json`
- `openmy skill transcript.confirm.submit --date YYYY-MM-DD --payload-file /tmp/openmy-confirm-YYYY-MM-DD.json --json`

## Restrictions

- Ask at most 5 uncertain items per round.
- Only ask about items that would change the daily briefing once settled. If an uncertain word appears in a throwaway remark that the summary already ignores, skip it.
- Never show file paths, JSON payloads, or technical identifiers to the user.
- Never ask the user to type commands.
- Keep questions short and in plain language.

## Output

- Start with `human_summary`.
- If items are pending, present them conversationally: show the uncertain word and its surrounding context, ask the user what the correct word is.
- If no items are pending, say so and move on.
- End with one concrete next step.

## Agent Behavior

1. Call `transcript.confirm.pending` after distillation completes.
2. If `data.status` is `no_items`, skip confirmation and continue to `extract.core.pending`.
3. If items exist, present each uncertain word with its context to the user.
4. For each item, the user can say:
   - The correct word (resolution: `corrected`, fill `wrong` and `right`).
   - The word is already correct (resolution: `confirmed_correct`, fill `wrong`).
   - They don't know (resolution: `unknown`, fill `wrong`).
5. Collect answers, save the payload to `/tmp/openmy-confirm-YYYY-MM-DD.json`.
6. Submit with `transcript.confirm.submit`.
7. After a successful submit, continue to `extract.core.pending`.
8. Clean up the temp payload file after a successful submit.

## Dialogue Style

- Present uncertain words naturally: "转写里有几个词我不太确定，帮我看看？"
- Show the word in context, not in isolation: "「去[宿州]看车」这里的「宿州」对吗？"
- Group all items in one message, numbered if more than two.
- Accept the user's verbal answer directly. Do not ask them to pick from a menu.

## Error Handling

If any command returns `ok: false`:
1. Read `error_code` and `message`.
2. Common recovery:
   - `missing_scenes` → rerun `day.run` with audio
   - `missing_items` → check that the payload has at least one item
3. Unknown errors should be surfaced plainly, then route to `openmy-health-check`.
