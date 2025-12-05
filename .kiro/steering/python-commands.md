---
inclusion: always
---

# Python Command Usage

## System-Specific Python Command

On this macOS system, the Python 3 interpreter is accessed via `python3`, not `python`.

**CRITICAL RULE**: Always use `python3` when executing Python commands.

### Correct Usage:
- `python3 -m pytest ...`
- `python3 script.py`
- `python3 -m pip install ...`
- `python3 -c "..."`

### Incorrect Usage (will fail):
- ~~`python -m pytest ...`~~
- ~~`python script.py`~~
- ~~`python -m pip install ...`~~

This applies to ALL Python command invocations in bash commands.
