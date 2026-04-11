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
- Do not guess the user's profile fields when they are unclear.
- Do not treat profile setup as a replacement for vocab setup.

## Output

- show the current or updated profile
- confirm which fields changed
- suggest the next onboarding step

## Agent Behavior

1. Ask for the name the user wants OpenMy to remember.
2. Ask what language answers should default to.
3. Ask for the correct timezone when timing matters.
4. After profile setup, route to `openmy-vocab-init` if vocab is not ready.
