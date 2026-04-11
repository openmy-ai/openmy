# OpenMy Vocab Init

## Purpose

Initialize the personal vocabulary files and help the agent gather names, products, and domain terms that speech-to-text often gets wrong.

## Trigger

Use it when:
- vocab files do not exist yet
- transcript errors keep showing up on names or terms
- the user is onboarding OpenMy for the first time
- a new proper noun appears often in conversation

## Action

- `openmy skill vocab.init --json`

## Restrictions

- Do not edit `vocab.txt` or `corrections.json` directly inside this skill.
- Do not write user-specific terms without confirmation.
- Do not skip asking about obvious names, projects, or tools.

## Output

- say whether files were created or already existed
- tell the user what kind of terms should go into vocab
- suggest the next onboarding move

## Agent Behavior

1. Ask which tools, apps, services, people, pets, brands, and projects show up often.
2. Mine prior conversation context for likely proper nouns.
3. Present candidates and ask for confirmation.
4. For each confirmed term, ask how speech-to-text might misspell it.
5. Use correction workflows only after the user confirms the term.
