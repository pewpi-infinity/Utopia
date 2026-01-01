#!/usr/bin/env python3
"""
Command-line interface for Utopia Deployer
"""

import sys
import argparse
import json
from deployer import Deployer, DeployerConfig


def cmd_deploy(args):
    """Handle deploy command"""
    config = DeployerConfig(args.config)
    deployer = Deployer(config)
    
    success = deployer.deploy(version=args.version)
    if success:
        print("✓ Deployment successful")
        return 0
    else:
        print("✗ Deployment failed")
        return 1


def cmd_rollback(args):
    """Handle rollback command"""
    config = DeployerConfig(args.config)
    deployer = Deployer(config)
    
    success = deployer.rollback(backup_name=args.backup)
    if success:
        print("✓ Rollback successful")
        return 0
    else:
        print("✗ Rollback failed")
        return 1


def cmd_status(args):
    """Handle status command"""
    config = DeployerConfig(args.config)
    deployer = Deployer(config)
    
    status = deployer.status()
    print(json.dumps(status, indent=2))
    return 0


def cmd_list_backups(args):
    """Handle list-backups command"""
    config = DeployerConfig(args.config)
    deployer = Deployer(config)
    
    backups = deployer.list_backups()
    if backups:
        print("Available backups:")
        for backup in backups:
            print(f"  - {backup}")
    else:
        print("No backups available")
    return 0


def cmd_init(args):
    """Handle init command"""
    config = DeployerConfig(args.config)
    config.save_config()
    print(f"✓ Configuration initialized at {args.config}")
    print(f"  Edit the file to customize deployment settings")
    return 0


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Utopia Deployer - Simple deployment automation tool"
    )
    parser.add_argument(
        '--config', '-c',
        default='deploy_config.json',
        help='Path to configuration file (default: deploy_config.json)'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy the application')
    deploy_parser.add_argument(
        '--version', '-v',
        help='Version identifier for this deployment'
    )
    deploy_parser.set_defaults(func=cmd_deploy)
    
    # Rollback command
    rollback_parser = subparsers.add_parser('rollback', help='Rollback to a previous deployment')
    rollback_parser.add_argument(
        '--backup', '-b',
        help='Specific backup to rollback to (default: most recent)'
    )
    rollback_parser.set_defaults(func=cmd_rollback)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show deployment status')
    status_parser.set_defaults(func=cmd_status)
    
    # List backups command
    list_parser = subparsers.add_parser('list-backups', help='List available backups')
    list_parser.set_defaults(func=cmd_list_backups)
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize configuration file')
    init_parser.set_defaults(func=cmd_init)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
