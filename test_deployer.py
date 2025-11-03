#!/usr/bin/env python3
"""
Tests for Utopia Deployer
"""

import os
import json
import shutil
import unittest
import tempfile
from pathlib import Path
from deployer import Deployer, DeployerConfig


class TestDeployerConfig(unittest.TestCase):
    """Test DeployerConfig class"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "test_config.json")
    
    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_default_config(self):
        """Test default configuration creation"""
        config = DeployerConfig(self.config_file)
        self.assertIn("app_name", config.config)
        self.assertIn("deploy_dir", config.config)
        self.assertEqual(config.get("app_name"), "utopia-app")
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration"""
        config = DeployerConfig(self.config_file)
        config.set("custom_key", "custom_value")
        config.save_config()
        
        # Load config again
        config2 = DeployerConfig(self.config_file)
        self.assertEqual(config2.get("custom_key"), "custom_value")
    
    def test_get_set_config(self):
        """Test getting and setting config values"""
        config = DeployerConfig(self.config_file)
        config.set("test_key", "test_value")
        self.assertEqual(config.get("test_key"), "test_value")
        self.assertIsNone(config.get("nonexistent_key"))
        self.assertEqual(config.get("nonexistent_key", "default"), "default")


class TestDeployer(unittest.TestCase):
    """Test Deployer class"""
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "test_config.json")
        
        # Create test directories
        self.source_dir = os.path.join(self.test_dir, "src")
        self.deploy_dir = os.path.join(self.test_dir, "deploy")
        self.backup_dir = os.path.join(self.test_dir, "backups")
        
        os.makedirs(self.source_dir)
        
        # Create config
        config = DeployerConfig(self.config_file)
        config.set("source_dir", self.source_dir)
        config.set("deploy_dir", self.deploy_dir)
        config.set("backup_dir", self.backup_dir)
        config.set("max_backups", 3)
        config.save_config()
        
        self.config = config
        self.deployer = Deployer(self.config)
    
    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_deployer_initialization(self):
        """Test deployer initialization"""
        self.assertIsNotNone(self.deployer)
        self.assertTrue(os.path.exists(self.deploy_dir))
        self.assertTrue(os.path.exists(self.backup_dir))
    
    def test_deploy_basic(self):
        """Test basic deployment"""
        # Create test file in source
        test_file = os.path.join(self.source_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")
        
        # Deploy
        success = self.deployer.deploy(version="1.0.0")
        self.assertTrue(success)
        
        # Verify deployment
        deployed_file = os.path.join(self.deploy_dir, "test.txt")
        self.assertTrue(os.path.exists(deployed_file))
        with open(deployed_file, 'r') as f:
            self.assertEqual(f.read(), "test content")
    
    def test_deploy_with_metadata(self):
        """Test deployment creates metadata"""
        # Create test file
        test_file = os.path.join(self.source_dir, "app.py")
        with open(test_file, 'w') as f:
            f.write("print('Hello')")
        
        # Deploy
        self.deployer.deploy(version="2.0.0")
        
        # Check metadata
        metadata_file = os.path.join(self.deploy_dir, ".deploy_metadata.json")
        self.assertTrue(os.path.exists(metadata_file))
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        self.assertEqual(metadata["version"], "2.0.0")
        self.assertIn("timestamp", metadata)
    
    def test_deploy_creates_backup(self):
        """Test that deployment creates backup of previous version"""
        # First deployment
        test_file1 = os.path.join(self.source_dir, "v1.txt")
        with open(test_file1, 'w') as f:
            f.write("version 1")
        self.deployer.deploy(version="1.0.0")
        
        # Second deployment
        os.remove(test_file1)
        test_file2 = os.path.join(self.source_dir, "v2.txt")
        with open(test_file2, 'w') as f:
            f.write("version 2")
        self.deployer.deploy(version="2.0.0")
        
        # Check backup exists
        backups = self.deployer.list_backups()
        self.assertEqual(len(backups), 1)
    
    def test_rollback(self):
        """Test rollback functionality"""
        # First deployment
        test_file1 = os.path.join(self.source_dir, "v1.txt")
        with open(test_file1, 'w') as f:
            f.write("version 1")
        self.deployer.deploy(version="1.0.0")
        
        # Second deployment
        os.remove(test_file1)
        test_file2 = os.path.join(self.source_dir, "v2.txt")
        with open(test_file2, 'w') as f:
            f.write("version 2")
        self.deployer.deploy(version="2.0.0")
        
        # Rollback
        success = self.deployer.rollback()
        self.assertTrue(success)
        
        # Verify old file is back
        restored_file = os.path.join(self.deploy_dir, "v1.txt")
        self.assertTrue(os.path.exists(restored_file))
        self.assertFalse(os.path.exists(os.path.join(self.deploy_dir, "v2.txt")))
    
    def test_status(self):
        """Test status reporting"""
        # Check status before deployment
        status = self.deployer.status()
        self.assertFalse(status["deployed"])
        
        # Deploy
        test_file = os.path.join(self.source_dir, "app.py")
        with open(test_file, 'w') as f:
            f.write("print('Hello')")
        self.deployer.deploy(version="1.0.0")
        
        # Check status after deployment
        status = self.deployer.status()
        self.assertTrue(status["deployed"])
        self.assertEqual(status["metadata"]["version"], "1.0.0")
    
    def test_max_backups_cleanup(self):
        """Test that old backups are cleaned up"""
        # Create multiple deployments
        for i in range(5):
            test_file = os.path.join(self.source_dir, f"v{i}.txt")
            with open(test_file, 'w') as f:
                f.write(f"version {i}")
            self.deployer.deploy(version=f"{i}.0.0")
            # Remove the file for next iteration
            if os.path.exists(test_file):
                os.remove(test_file)
        
        # Should only keep max_backups (3) backups
        backups = self.deployer.list_backups()
        self.assertLessEqual(len(backups), 3)
    
    def test_list_backups(self):
        """Test listing backups"""
        # No backups initially
        backups = self.deployer.list_backups()
        self.assertEqual(len(backups), 0)
        
        # Create a deployment to generate backup
        test_file = os.path.join(self.source_dir, "app.py")
        with open(test_file, 'w') as f:
            f.write("v1")
        self.deployer.deploy(version="1.0.0")
        
        # Create another deployment
        with open(test_file, 'w') as f:
            f.write("v2")
        self.deployer.deploy(version="2.0.0")
        
        # Should have one backup now
        backups = self.deployer.list_backups()
        self.assertEqual(len(backups), 1)


if __name__ == '__main__':
    unittest.main()
