# Utopia Deployer

A simple, yet powerful deployment automation tool for managing application deployments with built-in backup and rollback capabilities.

## Features

- **Simple Deployment**: Deploy applications with a single command
- **Automatic Backups**: Every deployment creates a backup of the previous version
- **Easy Rollback**: Quickly rollback to any previous deployment
- **Configuration Management**: Flexible JSON-based configuration
- **Deployment Hooks**: Run custom scripts before/after deploy and rollback operations
- **Status Tracking**: View current deployment status and metadata
- **Backup Management**: Automatic cleanup of old backups based on retention policy

## Installation

No external dependencies required! Just Python 3.6+

```bash
# Clone the repository
git clone https://github.com/pewpi-infinity/Utopia.git
cd Utopia

# Make CLI executable (optional)
chmod +x deploy_cli.py
```

## Quick Start

### 1. Initialize Configuration

```bash
python3 deploy_cli.py init
```

This creates a `deploy_config.json` file with default settings:

```json
{
  "app_name": "utopia-app",
  "deploy_dir": "./deployments",
  "source_dir": "./src",
  "backup_dir": "./backups",
  "max_backups": 5,
  "deployment_hooks": {
    "pre_deploy": [],
    "post_deploy": [],
    "pre_rollback": [],
    "post_rollback": []
  }
}
```

### 2. Prepare Your Application

Create a `src` directory and add your application files:

```bash
mkdir src
echo "print('Hello from Utopia!')" > src/app.py
```

### 3. Deploy

```bash
python3 deploy_cli.py deploy --version 1.0.0
```

### 4. Check Status

```bash
python3 deploy_cli.py status
```

### 5. Rollback (if needed)

```bash
python3 deploy_cli.py rollback
```

## Usage

### Command Line Interface

```bash
# Deploy application
python3 deploy_cli.py deploy [--version VERSION]

# Rollback to previous version
python3 deploy_cli.py rollback [--backup BACKUP_NAME]

# Show deployment status
python3 deploy_cli.py status

# List available backups
python3 deploy_cli.py list-backups

# Initialize configuration
python3 deploy_cli.py init
```

### Python API

```python
from deployer import Deployer, DeployerConfig

# Initialize deployer
config = DeployerConfig()
deployer = Deployer(config)

# Deploy application
success = deployer.deploy(version="1.0.0")

# Check status
status = deployer.status()
print(status)

# Rollback to previous version
deployer.rollback()

# List available backups
backups = deployer.list_backups()
```

## Configuration

Edit `deploy_config.json` to customize behavior:

- **app_name**: Name of your application
- **deploy_dir**: Directory where application will be deployed
- **source_dir**: Directory containing source files to deploy
- **backup_dir**: Directory to store backups
- **max_backups**: Maximum number of backups to retain (older backups are automatically deleted)
- **deployment_hooks**: Scripts to run at various stages:
  - `pre_deploy`: Before deployment starts
  - `post_deploy`: After successful deployment
  - `pre_rollback`: Before rollback starts
  - `post_rollback`: After successful rollback

### Example with Hooks

```json
{
  "app_name": "my-web-app",
  "deploy_dir": "/var/www/app",
  "source_dir": "./build",
  "backup_dir": "/var/backups/app",
  "max_backups": 10,
  "deployment_hooks": {
    "pre_deploy": [
      "echo 'Starting deployment...'",
      "npm run build"
    ],
    "post_deploy": [
      "sudo systemctl restart myapp",
      "curl -X POST https://api.example.com/notify-deploy"
    ],
    "pre_rollback": ["sudo systemctl stop myapp"],
    "post_rollback": ["sudo systemctl start myapp"]
  }
}
```

## Testing

Run the test suite:

```bash
python3 test_deployer.py
```

Run with verbose output:

```bash
python3 test_deployer.py -v
```

## Architecture

### Core Components

1. **DeployerConfig**: Manages configuration loading, saving, and access
2. **Deployer**: Main class handling deployment, rollback, and status operations
3. **CLI**: Command-line interface for easy interaction

### Deployment Process

1. Run pre-deploy hooks
2. Create backup of current deployment (if exists)
3. Clear deployment directory
4. Copy files from source to deployment directory
5. Save deployment metadata
6. Run post-deploy hooks

### Rollback Process

1. Run pre-rollback hooks
2. Identify backup to restore (most recent or specified)
3. Clear current deployment
4. Restore files from backup
5. Run post-rollback hooks

## Use Cases

- **Web Applications**: Deploy web apps with zero-downtime rollback capability
- **Microservices**: Manage individual service deployments
- **Configuration Management**: Deploy configuration updates with version control
- **Static Sites**: Deploy and manage static website versions
- **Development Environments**: Quickly switch between different application versions

## Best Practices

1. **Version Tagging**: Always use meaningful version identifiers
2. **Pre-Deploy Testing**: Test in a staging environment before production deployment
3. **Hook Usage**: Use hooks for service restarts, cache clearing, health checks
4. **Backup Retention**: Adjust `max_backups` based on your storage and requirements
5. **Monitoring**: Monitor deployment logs for any issues

## Troubleshooting

### Deployment fails with permission errors
- Ensure you have write permissions to deploy_dir and backup_dir
- Run with appropriate user privileges

### Rollback doesn't restore all files
- Check that backups are being created successfully
- Verify backup_dir has sufficient space

### Hooks fail silently
- Check hook commands are valid shell commands
- Review deployer logs for error messages

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT License - see LICENSE file for details

## Support

For questions or issues, please open an issue on GitHub.