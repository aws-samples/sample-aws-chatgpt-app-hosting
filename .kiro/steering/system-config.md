# System Configuration

## Docker Setup

On this system, Docker is aliased to Finch in the `.zshrc` file.

**CRITICAL**: When running Docker commands, use `finch` instead of `docker`.

### Examples:
- `finch ps` (instead of `docker ps`)
- `finch build -t myimage .` (instead of `docker build -t myimage .`)
- `finch run ...` (instead of `docker run ...`)

### CDK Deployment
When CDK needs Docker for bundling assets, it will automatically use the system's Docker configuration (which aliases to Finch), so CDK commands should work as-is.

## Python Command

The Python 3 interpreter is accessed via `python3`, not `python`.
