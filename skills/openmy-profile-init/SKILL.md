---
name: openmy-profile-init
description: Use when creating or updating the user's profile (name, language, timezone)
---

# OpenMy Profile Init

## Purpose

Create or update the user's basic profile so context snapshots know the correct name, language, and timezone.

## Trigger

Use it when:
- this is first-time setup
- profile data is missing
- the user changes name, language, or timezone
- onboarding needs a stable identity layer

## Action

- `openmy skill profile.get --json`
- `openmy skill profile.set --name "User Name" --language zh-CN --timezone Asia/Shanghai --json`

## Restrictions

- Do not edit `profile.json` directly.
- Do not treat profile setup as a replacement for vocab setup.

## Output

- show the current or updated profile
- confirm which fields changed
- suggest the next onboarding step

## Agent Behavior

**Do NOT ask the user for profile fields one by one.** Auto-detect and set them in one shot.

1. Run `profile.get` to check the current profile.
2. If the profile still has default values (`name=User`, `language=en`, `timezone=UTC`), auto-detect from the system:
   - **Language**: Detect from the conversation language or system locale. If the user speaks Chinese, use `zh-CN`. If English, use `en`.
   - **Timezone**: Run a shell command to detect the system timezone (e.g., `date +%Z` or read `/etc/localtime`). Common results: `Asia/Shanghai`, `America/New_York`, `Europe/London`, etc.
   - **Name**: Use the system username as a starting point (e.g., from `whoami` or `$USER`). This is a fallback — the name is not critical.
3. Run `profile.set` with the detected values in one command. Do not ask permission first — just do it.
4. Tell the user: "I set up your profile with [language] and [timezone]. You can change it anytime."
5. After profile setup, route to `openmy-vocab-init` if vocab is not ready.
