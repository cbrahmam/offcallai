# OffCall CLI

Command-line interface for OffCall AI - the AI-powered observability and incident management platform.

## Installation

```bash
pip install offcall-cli
```

## Quick Start

```bash
# Configure with your API key
offcall configure

# List open incidents
offcall incidents list --status=open

# Check who's on-call
offcall oncall who

# Notify about a deployment
offcall deploy notify --service=api --version=1.2.3
```

## Commands

### Incidents

```bash
# List incidents
offcall incidents list
offcall incidents list --status=open --severity=critical

# Show incident details
offcall incidents show INCIDENT_ID

# Acknowledge an incident
offcall incidents ack INCIDENT_ID

# Resolve an incident
offcall incidents resolve INCIDENT_ID
```

### Alerts

```bash
# List alerts
offcall alerts list
offcall alerts list --severity=high

# Acknowledge an alert
offcall alerts ack ALERT_ID
```

### On-Call

```bash
# Who is currently on-call?
offcall oncall who

# List schedules
offcall oncall schedule
```

### Deployments

```bash
# Notify about a deployment (for CI/CD integration)
offcall deploy notify \
  --service=api \
  --version=1.2.3 \
  --environment=production \
  --commit=abc123 \
  --message="Fix login bug" \
  --branch=main

# List recent deployments
offcall deploy list --service=api
```

### Hosts

```bash
# List hosts
offcall hosts list
offcall hosts list --status=inactive

# Show host details
offcall hosts show HOST_ID
```

### Logs

```bash
# Search logs
offcall logs search "error"
offcall logs search "timeout" --service=api --level=error --last=1h
```

### Services

```bash
# List services
offcall services list
```

## Configuration

### API Key

Configure your API key:

```bash
offcall configure
```

Or use environment variables:

```bash
export OFFCALL_API_KEY=your_api_key
export OFFCALL_API_URL=http://localhost:8000/api/v1  # optional
```

### Multiple Profiles

Use different profiles for different environments:

```bash
# Configure staging profile
offcall --profile=staging configure

# Use staging profile
offcall --profile=staging incidents list
```

### Config File

Configuration is stored in `~/.offcall/config.yaml`:

```yaml
default:
  api_url: http://localhost:8000/api/v1
  api_key: ofc_xxxxxxxxxxxx

staging:
  api_url: https://offcall.staging.internal/api/v1
  api_key: ofc_staging_key
```

## CI/CD Integration

### GitHub Actions

```yaml
- name: Notify OffCall of deployment
  run: |
    pip install offcall-cli
    offcall deploy notify \
      --service=${{ github.repository }} \
      --version=${{ github.sha }} \
      --commit=${{ github.sha }} \
      --branch=${{ github.ref_name }}
  env:
    OFFCALL_API_KEY: ${{ secrets.OFFCALL_API_KEY }}
```

### GitLab CI

```yaml
notify_deployment:
  script:
    - pip install offcall-cli
    - offcall deploy notify --service=$CI_PROJECT_NAME --version=$CI_COMMIT_SHA
  variables:
    OFFCALL_API_KEY: $OFFCALL_API_KEY
```

### Jenkins

```groovy
pipeline {
    environment {
        OFFCALL_API_KEY = credentials('offcall-api-key')
    }
    stages {
        stage('Notify') {
            steps {
                sh 'pip install offcall-cli'
                sh 'offcall deploy notify --service=${JOB_NAME} --version=${BUILD_NUMBER}'
            }
        }
    }
}
```

## Output Formats

The CLI uses rich formatting for terminal output. For machine-readable output in scripts, pipe to `jq` or similar tools.

## Requirements

- Python 3.8+
- Works on Linux, macOS, and Windows

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- [Documentation](https://github.com/cbrahmam/offcallai/blob/main/cli/README.md)
- OffCall AI
- [GitHub](https://github.com/offcall-ai/offcall-cli)
- [PyPI](https://pypi.org/project/offcall-cli/)
