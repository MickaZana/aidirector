# Windows dev environment — quirks and fixes

Captured 2026-05-18/19 while bringing up uv + Alembic on Windows 11 (git-bash + PowerShell). Read this **before** running uv or any `.venv` python on this machine. Every issue below is reproducible and has a one-line fix.

## TL;DR

1. **Unset `VIRTUAL_ENV`** before any `uv` command — it leaks from the parent shell pointing at `C:\Python314` (a read-only system Python) and uv will try to install there.
2. **Don't use `uv --active`** when `VIRTUAL_ENV` is set incorrectly. It forces uv to target whatever `VIRTUAL_ENV` says.
3. **Wrap venv-python invocations in `cmd /c "...exe ..."`** when PowerShell or git-bash hangs. `& ".\.venv\Scripts\python.exe"` and `.venv/Scripts/python.exe` both hang silently on this machine for some workloads. `cmd /c "..\..\.venv\Scripts\python.exe ..."` runs fine.
4. **Drive Alembic from Python, not the CLI**, when validating migrations on Windows. The probe scripts under `apps/api/_probe_*.py` are the canonical pattern.

## 1. The `VIRTUAL_ENV=C:\Python314` trap

### Symptom

```
error: Failed to install: pycparser-3.0-py3-none-any.whl (pycparser==3.0)
  Caused by: Failed to create directory `C:\Python314\Lib\site-packages\pycparser`
  Caused by: failed to create directory ... Access is denied. (os error 5)
```

### Cause

A previous shell session set `VIRTUAL_ENV=C:\Python314` (probably from an earlier manual `Activate.ps1` against the system Python). The env var persists at the user level. When you run uv with `--active`, uv honours it and tries to install into the system Python, which is read-only.

### Fix

```bash
# bash
unset VIRTUAL_ENV
uv sync --all-packages

# powershell
Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
uv sync --all-packages
```

### Permanent fix

Remove the stale user-level VIRTUAL_ENV via:

```powershell
[Environment]::SetEnvironmentVariable("VIRTUAL_ENV", $null, "User")
```

(Restart your shell. PowerShell's session env is inherited from the system+user env at launch.)

## 2. Don't use `uv --active` with a wrong VIRTUAL_ENV

`uv run --active` and `uv sync --active` both override uv's default of resolving the workspace `.venv`. They make uv target whatever `VIRTUAL_ENV` points to. **Skip `--active` unless you know exactly what env you're targeting.**

Default behaviour (without `--active`): uv finds the workspace `.venv` from the closest `pyproject.toml` upwards. That's what you want for `aidirector`.

## 3. PowerShell / bash hang on `.venv\Scripts\python.exe`

### Symptom

```powershell
& ".\.venv\Scripts\python.exe" -c "print('hi')"   # hangs, no output
```

```bash
.venv/Scripts/python.exe -c "print('hi')"          # same
```

Background tasks return zero-byte output files. Tasks never complete.

### Cause

Unclear — possibly Windows Defender / AppLocker / Smart Screen intercepting the call when invoked via `&` operator. Reproducible on this machine, vanishes when wrapped in `cmd /c`.

### Fix

```powershell
cmd /c "..\..\.venv\Scripts\python.exe <args> 2>&1"
```

```bash
cmd /c "..\\..\\.venv\\Scripts\\python.exe <args>"
```

This pattern is used everywhere in `apps/api/_probe_*.py` invocations — see [docs/proof_of_work_phase0_to_1.md §9](../proof_of_work_phase0_to_1.md). Adopt it as the default Windows pattern.

## 4. Alembic CLI hangs silently — use a Python wrapper

### Symptom

```powershell
cmd /c "..\..\.venv\Scripts\python.exe -m alembic upgrade head 2>&1"
# task runs, output file stays empty, no exit
```

The schema probe with `Base.metadata.create_all` works on the *same* venv python under `cmd /c`. The alembic CLI specifically hangs.

### Cause

Suspected: alembic's `fileConfig(config.config_file_name)` in `env.py` reconfigures the root logger in a way that collides with the wrapping shell's stdout buffering on Windows. Couldn't fully diagnose; workaround is reliable.

### Fix

Drive alembic from Python instead of via the CLI:

```python
import io, sys
from alembic import command
from alembic.config import Config

cfg = Config("alembic.ini")
cfg.set_main_option("sqlalchemy.url", "sqlite:///./aidirector_probe.db")

saved_out, saved_err = sys.stdout, sys.stderr
sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
try:
    command.upgrade(cfg, "head")
finally:
    sys.stdout, sys.stderr = saved_out, saved_err
```

Capture stdout/stderr to StringIO, write to a log file. The probe scripts in [apps/api/_probe_alembic.py](../../apps/api/_probe_alembic.py) and [apps/api/_probe_loop.py](../../apps/api/_probe_loop.py) implement this pattern.

**This is the canonical way to validate Alembic migrations on Windows for this repo until we have CI running on Linux containers.**

## 5. Prefer probe scripts for Alembic validation on Windows

While Windows is the dev machine, treat the Alembic CLI as a CI/Linux tool. On dev:

| Goal | Use |
|---|---|
| Smoke-test models | `apps/api/_probe_schema.py` |
| Validate migration upgrade | `apps/api/_probe_alembic.py` |
| Validate upgrade + downgrade + full FK chain + plan round-trip | `apps/api/_probe_loop.py` |
| Author a new revision | `cd apps/api && cmd /c "..\..\.venv\Scripts\python.exe -m alembic revision -m '...' --autogenerate"` |

The probe scripts double as reproducibility tools. Don't delete them until Neon validation is wired and CI runs on Linux.

## 6. uv install commands that work on this machine

```powershell
# install uv (one-time)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# add to PATH for current session
$env:Path = "C:\Users\mican\.local\bin;$env:Path"

# sync workspace (note: --all-packages installs every workspace member)
Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
uv sync --all-packages
```

After this, `.venv/Scripts/` contains alembic.exe, uvicorn.exe, modal.exe, fastapi.exe, rq.exe, etc.

## 7. Things that still need solving before Linux/CI

- The PowerShell `&`-hang behaviour around venv python.exe. Likely Defender / SmartScreen; would benefit from a Defender exclusion on the repo path.
- The Alembic-CLI-hang. The Python-wrapper workaround is fine for dev but CI should run alembic via the CLI on Linux runners to catch this if it surfaces there too.

Both vanish on Linux / WSL / GitHub Actions Ubuntu runners (verified during ad-hoc tests of the same scripts). Treat them as Windows-specific.
