# Installing OpenMy Skills for Codex

Enable OpenMy skills in Codex via native skill discovery. Clone and symlink.

## Prerequisites

- Git

## Installation

1. **Clone the OpenMy repository (if not already cloned):**
   ```bash
   git clone https://github.com/openmy-ai/openmy.git ~/.codex/openmy
   ```

2. **Create the skills symlink:**
   ```bash
   mkdir -p ~/.agents/skills
   ln -s ~/.codex/openmy/skills ~/.agents/skills/openmy
   ```

   **Windows (PowerShell):**
   ```powershell
   New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.agents\skills"
   cmd /c mklink /J "$env:USERPROFILE\.agents\skills\openmy" "$env:USERPROFILE\.codex\openmy\skills"
   ```

3. **Restart Codex** (quit and relaunch the CLI) to discover the skills.

## If You Already Have the Repo Locally

If you cloned OpenMy somewhere else (e.g. for development), just symlink from there:

```bash
mkdir -p ~/.agents/skills
ln -s /path/to/your/openmy/skills ~/.agents/skills/openmy
```

## Verify

```bash
ls -la ~/.agents/skills/openmy
```

You should see a symlink pointing to the OpenMy skills directory.

## Updating

```bash
cd ~/.codex/openmy && git pull
```

Skills update instantly through the symlink.

## Uninstalling

```bash
rm ~/.agents/skills/openmy
```

Optionally delete the clone: `rm -rf ~/.codex/openmy`.
