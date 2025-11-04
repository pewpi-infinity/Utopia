#!/usr/bin/env python3
"""
Demo script for Utopia Deployer

This script demonstrates the basic usage of the Utopia Deployer.
"""

import os
import shutil
import tempfile
from deployer import Deployer, DeployerConfig


def demo():
    """Run deployment demo"""
    print("=" * 60)
    print("Utopia Deployer - Demo")
    print("=" * 60)
    print()
    
    # Create a temporary directory for demo
    demo_dir = tempfile.mkdtemp(prefix="utopia_demo_")
    print(f"Demo directory: {demo_dir}")
    print()
    
    try:
        # Setup directories
        src_dir = os.path.join(demo_dir, "src")
        deploy_dir = os.path.join(demo_dir, "deployments")
        backup_dir = os.path.join(demo_dir, "backups")
        config_file = os.path.join(demo_dir, "config.json")
        
        os.makedirs(src_dir)
        
        # Create configuration
        config = DeployerConfig(config_file)
        config.set("source_dir", src_dir)
        config.set("deploy_dir", deploy_dir)
        config.set("backup_dir", backup_dir)
        config.set("max_backups", 3)
        config.save_config()
        
        # Create deployer
        deployer = Deployer(config)
        
        # Step 1: Create initial application version
        print("Step 1: Creating initial application (v1.0.0)")
        print("-" * 60)
        with open(os.path.join(src_dir, "app.py"), 'w') as f:
            f.write("print('Hello from version 1.0.0')\n")
        with open(os.path.join(src_dir, "config.txt"), 'w') as f:
            f.write("version=1.0.0\n")
        
        success = deployer.deploy(version="1.0.0")
        print(f"Deployment status: {'✓ SUCCESS' if success else '✗ FAILED'}")
        print()
        
        # Step 2: Show deployment status
        print("Step 2: Checking deployment status")
        print("-" * 60)
        status = deployer.status()
        print(f"Deployed: {status['deployed']}")
        print(f"Version: {status['metadata']['version']}")
        print()
        
        # Step 3: Create and deploy version 2
        print("Step 3: Deploying version 2.0.0")
        print("-" * 60)
        with open(os.path.join(src_dir, "app.py"), 'w') as f:
            f.write("print('Hello from version 2.0.0 - Now with new features!')\n")
        with open(os.path.join(src_dir, "config.txt"), 'w') as f:
            f.write("version=2.0.0\nenabled_features=new_ui,dark_mode\n")
        
        success = deployer.deploy(version="2.0.0")
        print(f"Deployment status: {'✓ SUCCESS' if success else '✗ FAILED'}")
        print()
        
        # Step 4: List backups
        print("Step 4: Listing available backups")
        print("-" * 60)
        backups = deployer.list_backups()
        for i, backup in enumerate(backups, 1):
            print(f"{i}. {backup}")
        print()
        
        # Step 5: Show current deployment
        print("Step 5: Current deployment content")
        print("-" * 60)
        app_file = os.path.join(deploy_dir, "app.py")
        with open(app_file, 'r') as f:
            print(f.read())
        print()
        
        # Step 6: Rollback to version 1
        print("Step 6: Rolling back to previous version")
        print("-" * 60)
        success = deployer.rollback()
        print(f"Rollback status: {'✓ SUCCESS' if success else '✗ FAILED'}")
        print()
        
        # Step 7: Show deployment after rollback
        print("Step 7: Deployment content after rollback")
        print("-" * 60)
        with open(app_file, 'r') as f:
            print(f.read())
        print()
        
        # Step 8: Final status
        print("Step 8: Final deployment status")
        print("-" * 60)
        status = deployer.status()
        print(f"Deployed: {status['deployed']}")
        if status['metadata']:
            print(f"Version: {status['metadata']['version']}")
        print(f"Available backups: {len(status['available_backups'])}")
        print()
        
    finally:
        # Cleanup
        print("=" * 60)
        print("Demo completed!")
        print(f"Cleaning up: {demo_dir}")
        shutil.rmtree(demo_dir)
        print("=" * 60)


if __name__ == "__main__":
    demo()
