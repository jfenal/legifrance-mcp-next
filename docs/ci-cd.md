# Continuous Integration & Deployment

This project uses GitHub Actions for automated CI/CD workflows to ensure code quality, security, and reliability.

## CI/CD Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| **Tests** | Push to main, PRs | Run test suite with coverage (90% minimum) |
| **Pre-commit** | Push to main, PRs | Linting, formatting, type checking, security scans |
| **Labeler** | PR opened/updated | Auto-label PRs by changed file paths |
| **Release** | Tag push (`v*`) | Create GitHub Release with auto-generated notes |
| **Stale** | Weekly (Monday) | Mark and close inactive issues/PRs |
| **Dependabot** | Weekly (Monday) | Automated dependency update PRs |

## CI Pipeline Features

### Code Quality Assurance
- Multi-Python version testing (3.12, 3.13)
- Comprehensive test suite execution
- Code coverage reporting (90%+ requirement)
- Ruff linting and formatting validation
- MyPy type checking
- Docstring validation with pydocstyle

### Security & Compliance
- Bandit security linting
- Safety dependency vulnerability scanning

### Automation & Maintenance
- Dependabot configuration for automated dependency updates
- Pre-commit hook automation
- Weekly security audits
- Automated PR creation for dependency updates

### Concurrency Controls
All workflows include concurrency blocks to prevent redundant runs:
- PR workflows cancel in-progress runs when new commits are pushed
- Release workflows always run to completion
- Stale bot is limited to one concurrent run

## Running CI Checks Locally

Before pushing code, run the same checks that CI runs:

```bash
# Install development dependencies
uv pip install -e ".[dev]"

# Run all pre-commit checks
pre-commit run --all-files

# Run tests with coverage
pytest --cov=legifrance_mcp --cov-fail-under=80

# Run security checks
bandit -r legifrance_mcp/
safety check

# Build and test container
podman build -t legifrance-mcp .
podman run --rm legifrance-mcp python -c "import legifrance_mcp; print('OK')"
```

## Branch Protection

The `main` branch is protected with the following requirements:
- All CI checks must pass
- Pull request reviews required
- Up-to-date branches required
- No direct pushes to main
