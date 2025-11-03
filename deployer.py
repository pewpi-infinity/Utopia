#!/usr/bin/env python3
"""
Utopia Deployer - A simple deployment automation tool
"""

import os
import json
import logging
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List


class DeployerConfig:
    """Configuration management for the deployer"""
    
    def __init__(self, config_file: str = "deploy_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """Return default configuration"""
        return {
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
    
    def save_config(self):
        """Save current configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key: str, default=None):
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set(self, key: str, value):
        """Set configuration value"""
        self.config[key] = value


class Deployer:
    """Main deployer class for managing deployments"""
    
    def __init__(self, config: Optional[DeployerConfig] = None):
        self.config = config or DeployerConfig()
        self.logger = self._setup_logger()
        self._ensure_directories()
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger("Deployer")
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _ensure_directories(self):
        """Ensure required directories exist"""
        dirs = [
            self.config.get("deploy_dir"),
            self.config.get("backup_dir")
        ]
        for directory in dirs:
            os.makedirs(directory, exist_ok=True)
    
    def _run_hooks(self, hook_type: str):
        """Run deployment hooks"""
        hooks = self.config.get("deployment_hooks", {}).get(hook_type, [])
        for hook in hooks:
            self.logger.info(f"Running {hook_type} hook: {hook}")
            try:
                result = subprocess.run(
                    hook, shell=True, check=True, 
                    capture_output=True, text=True
                )
                self.logger.debug(f"Hook output: {result.stdout}")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Hook failed: {e.stderr}")
                raise
    
    def _create_backup(self) -> Optional[str]:
        """Create backup of current deployment"""
        deploy_dir = self.config.get("deploy_dir")
        backup_dir = self.config.get("backup_dir")
        
        if not os.path.exists(deploy_dir) or not os.listdir(deploy_dir):
            self.logger.info("No existing deployment to backup")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"backup_{timestamp}")
        
        self.logger.info(f"Creating backup at {backup_path}")
        shutil.copytree(deploy_dir, backup_path)
        
        self._cleanup_old_backups()
        return backup_path
    
    def _cleanup_old_backups(self):
        """Remove old backups beyond max_backups limit"""
        backup_dir = self.config.get("backup_dir")
        max_backups = self.config.get("max_backups", 5)
        
        backups = sorted(
            [os.path.join(backup_dir, d) for d in os.listdir(backup_dir)
             if os.path.isdir(os.path.join(backup_dir, d))],
            key=os.path.getmtime,
            reverse=True
        )
        
        for backup in backups[max_backups:]:
            self.logger.info(f"Removing old backup: {backup}")
            shutil.rmtree(backup)
    
    def deploy(self, version: Optional[str] = None) -> bool:
        """
        Deploy the application
        
        Args:
            version: Optional version identifier for the deployment
        
        Returns:
            bool: True if deployment successful, False otherwise
        """
        try:
            self.logger.info("Starting deployment process")
            
            # Run pre-deploy hooks
            self._run_hooks("pre_deploy")
            
            # Create backup of current deployment
            backup_path = self._create_backup()
            
            # Copy source to deploy directory
            source_dir = self.config.get("source_dir")
            deploy_dir = self.config.get("deploy_dir")
            
            if not os.path.exists(source_dir):
                self.logger.error(f"Source directory not found: {source_dir}")
                return False
            
            # Clear deploy directory
            if os.path.exists(deploy_dir):
                for item in os.listdir(deploy_dir):
                    item_path = os.path.join(deploy_dir, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
            
            # Copy new files
            self.logger.info(f"Deploying from {source_dir} to {deploy_dir}")
            for item in os.listdir(source_dir):
                src_path = os.path.join(source_dir, item)
                dst_path = os.path.join(deploy_dir, item)
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dst_path)
                else:
                    shutil.copy2(src_path, dst_path)
            
            # Save deployment metadata
            metadata = {
                "version": version or "latest",
                "timestamp": datetime.now().isoformat(),
                "backup": backup_path
            }
            metadata_file = os.path.join(deploy_dir, ".deploy_metadata.json")
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            # Run post-deploy hooks
            self._run_hooks("post_deploy")
            
            self.logger.info("Deployment completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Deployment failed: {e}")
            return False
    
    def rollback(self, backup_name: Optional[str] = None) -> bool:
        """
        Rollback to a previous deployment
        
        Args:
            backup_name: Optional specific backup to rollback to.
                        If not provided, uses the most recent backup.
        
        Returns:
            bool: True if rollback successful, False otherwise
        """
        try:
            self.logger.info("Starting rollback process")
            
            # Run pre-rollback hooks
            self._run_hooks("pre_rollback")
            
            backup_dir = self.config.get("backup_dir")
            
            if backup_name:
                backup_path = os.path.join(backup_dir, backup_name)
            else:
                # Get most recent backup
                backups = sorted(
                    [os.path.join(backup_dir, d) for d in os.listdir(backup_dir)
                     if os.path.isdir(os.path.join(backup_dir, d))],
                    key=os.path.getmtime,
                    reverse=True
                )
                if not backups:
                    self.logger.error("No backups available for rollback")
                    return False
                backup_path = backups[0]
            
            if not os.path.exists(backup_path):
                self.logger.error(f"Backup not found: {backup_path}")
                return False
            
            deploy_dir = self.config.get("deploy_dir")
            
            # Clear current deployment
            if os.path.exists(deploy_dir):
                shutil.rmtree(deploy_dir)
            
            # Restore from backup
            self.logger.info(f"Restoring from backup: {backup_path}")
            shutil.copytree(backup_path, deploy_dir)
            
            # Run post-rollback hooks
            self._run_hooks("post_rollback")
            
            self.logger.info("Rollback completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Rollback failed: {e}")
            return False
    
    def status(self) -> Dict:
        """
        Get current deployment status
        
        Returns:
            Dict: Current deployment information
        """
        deploy_dir = self.config.get("deploy_dir")
        metadata_file = os.path.join(deploy_dir, ".deploy_metadata.json")
        
        status_info = {
            "deployed": os.path.exists(deploy_dir) and os.listdir(deploy_dir),
            "deploy_dir": deploy_dir,
            "metadata": None
        }
        
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                status_info["metadata"] = json.load(f)
        
        # Get available backups
        backup_dir = self.config.get("backup_dir")
        if os.path.exists(backup_dir):
            backups = sorted(
                [d for d in os.listdir(backup_dir)
                 if os.path.isdir(os.path.join(backup_dir, d))],
                reverse=True
            )
            status_info["available_backups"] = backups
        else:
            status_info["available_backups"] = []
        
        return status_info
    
    def list_backups(self) -> List[str]:
        """
        List all available backups
        
        Returns:
            List[str]: List of backup names
        """
        backup_dir = self.config.get("backup_dir")
        if not os.path.exists(backup_dir):
            return []
        
        backups = sorted(
            [d for d in os.listdir(backup_dir)
             if os.path.isdir(os.path.join(backup_dir, d))],
            reverse=True
        )
        return backups


if __name__ == "__main__":
    # Basic usage example
    deployer = Deployer()
    print("Deployer initialized")
    print(f"Status: {deployer.status()}")
