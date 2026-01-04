"""
Tests for recent files management.

Tests the RecentFileManager class and its integration with the GUI.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from workforce.gui.recent import RecentFileManager


class TestRecentFileManager:
    """Test RecentFileManager functionality."""

    @pytest.fixture
    def temp_data_dir(self):
        """Create a temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def temp_workfile(self):
        """Create a temporary workflow file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.wf', delete=False) as f:
            f.write("test")
            temp_file = f.name
        yield temp_file
        # Cleanup
        try:
            os.unlink(temp_file)
        except:
            pass

    def test_init_creates_manager(self):
        """Test that RecentFileManager initializes correctly."""
        rm = RecentFileManager()
        assert rm.data_dir is not None
        assert rm.recent_path is not None
        assert rm.MAX_RECENT == 20

    def test_load_empty_returns_list(self):
        """Test that load() returns empty list when file doesn't exist."""
        rm = RecentFileManager()
        # Remove file if it exists for this test
        if rm.recent_path.exists():
            rm.recent_path.unlink()
        
        result = rm.load()
        assert isinstance(result, list)
        assert len(result) == 0

    def test_save_creates_file(self):
        """Test that save() creates the JSON file."""
        rm = RecentFileManager()
        test_files = ["/path/to/file1.wf", "/path/to/file2.wf"]
        
        rm.save(test_files)
        
        assert rm.recent_path.exists()
        with open(rm.recent_path, 'r') as f:
            data = json.load(f)
        assert data["recent_files"] == test_files

    def test_add_single_file(self, temp_workfile):
        """Test adding a single file to recent list."""
        rm = RecentFileManager()
        rm.save([])  # Start fresh
        
        result = rm.add(temp_workfile)
        
        assert len(result) == 1
        assert os.path.abspath(temp_workfile) in result[0]

    def test_add_multiple_files_preserves_order(self, temp_workfile):
        """Test that adding multiple files preserves order (newest first)."""
        rm = RecentFileManager()
        rm.save([])
        
        # Create multiple temp files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.wf', delete=False) as f1:
            file1 = f1.name
            f1.write("test1")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.wf', delete=False) as f2:
            file2 = f2.name
            f2.write("test2")
        
        try:
            rm.add(file1)
            result = rm.add(file2)
            
            # Most recent should be first
            assert os.path.abspath(file2) in result[0]
            assert os.path.abspath(file1) in result[1]
        finally:
            try:
                os.unlink(file1)
                os.unlink(file2)
            except:
                pass

    def test_add_removes_duplicates(self, temp_workfile):
        """Test that adding same file twice removes the duplicate."""
        rm = RecentFileManager()
        rm.save([])
        
        rm.add(temp_workfile)
        result = rm.add(temp_workfile)
        
        # Should have exactly 1 item
        assert len(result) == 1

    def test_add_trims_to_max(self, temp_workfile):
        """Test that adding beyond MAX_RECENT trims the list."""
        rm = RecentFileManager()
        rm.save([])
        
        # Create many temp files
        temp_files = []
        try:
            for i in range(rm.MAX_RECENT + 5):
                with tempfile.NamedTemporaryFile(mode='w', suffix='.wf', delete=False) as f:
                    f.write(f"test{i}")
                    temp_files.append(f.name)
                rm.add(f.name)
            
            result = rm.load()
            assert len(result) <= rm.MAX_RECENT
        finally:
            for f in temp_files:
                try:
                    os.unlink(f)
                except:
                    pass

    def test_get_list_validates_paths(self):
        """Test that get_list() removes non-existent files."""
        rm = RecentFileManager()
        
        # Create a list with one real and one fake file
        real_file = "/tmp/real_test_file.wf"
        fake_file = "/tmp/fake_nonexistent_file_xyz.wf"
        
        # Create the real file
        with open(real_file, 'w') as f:
            f.write("test")
        
        try:
            # Manually set a list with both
            rm.save([real_file, fake_file])
            
            # get_list should filter out fake_file
            result = rm.get_list()
            
            assert len(result) == 1
            assert real_file in result[0]
            
            # Verify fake file was removed from persisted list
            loaded = rm.load()
            assert fake_file not in loaded
        finally:
            try:
                os.unlink(real_file)
            except:
                pass

    def test_remove_file(self, temp_workfile):
        """Test removing a file from recent list."""
        rm = RecentFileManager()
        rm.save([])
        
        # Add a file
        rm.add(temp_workfile)
        assert len(rm.load()) == 1
        
        # Remove it
        result = rm.remove(temp_workfile)
        
        assert len(result) == 0
        assert len(rm.load()) == 0

    def test_move_to_top(self, temp_workfile):
        """Test moving a file to the top of recent list."""
        rm = RecentFileManager()
        rm.save([])
        
        # Create two files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.wf', delete=False) as f1:
            file1 = f1.name
            f1.write("test1")
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.wf', delete=False) as f2:
            file2 = f2.name
            f2.write("test2")
        
        try:
            rm.add(file1)
            rm.add(file2)
            
            # Move file1 to top
            result = rm.move_to_top(file1)
            
            # file1 should be first
            assert os.path.abspath(file1) in result[0]
        finally:
            try:
                os.unlink(file1)
                os.unlink(file2)
            except:
                pass

    def test_persistence_across_instances(self, temp_workfile):
        """Test that data persists across RecentFileManager instances."""
        # Add file with first instance
        rm1 = RecentFileManager()
        rm1.save([])
        rm1.add(temp_workfile)
        
        # Load with second instance
        rm2 = RecentFileManager()
        result = rm2.load()
        
        assert len(result) > 0
        assert os.path.abspath(temp_workfile) in result[0]

    def test_json_format_is_valid(self):
        """Test that the saved JSON format is correct and valid."""
        rm = RecentFileManager()
        test_files = ["/path/to/file1.wf", "/path/to/file2.wf"]
        
        rm.save(test_files)
        
        # Verify JSON structure
        with open(rm.recent_path, 'r') as f:
            data = json.load(f)
        
        assert "recent_files" in data
        assert isinstance(data["recent_files"], list)
        assert data["recent_files"] == test_files

    def test_handles_absolute_path_normalization(self, temp_workfile):
        """Test that relative and absolute paths are normalized correctly."""
        rm = RecentFileManager()
        rm.save([])
        
        # Get absolute path
        abs_path = os.path.abspath(temp_workfile)
        
        # Change to directory containing file and use relative path
        original_cwd = os.getcwd()
        try:
            os.chdir(os.path.dirname(temp_workfile))
            rel_path = os.path.basename(temp_workfile)
            
            # Add using relative path
            rm.add(rel_path)
            
            # Should be stored as absolute
            result = rm.load()
            assert abs_path in result[0]
        finally:
            os.chdir(original_cwd)

    def test_handles_corrupted_json(self):
        """Test that corrupted JSON file is handled gracefully."""
        rm = RecentFileManager()
        
        # Create a corrupted JSON file
        rm.data_dir.mkdir(parents=True, exist_ok=True)
        with open(rm.recent_path, 'w') as f:
            f.write("{invalid json content")
        
        # Should return empty list instead of crashing
        result = rm.load()
        assert isinstance(result, list)
        assert len(result) == 0

    def test_handles_missing_directory(self):
        """Test that missing data directory is created on save."""
        # Create a new manager with a temp directory path that doesn't exist yet
        rm = RecentFileManager()
        
        # Remove the data directory if it exists
        if rm.data_dir.exists():
            shutil.rmtree(rm.data_dir)
        
        # Save should create the directory
        rm.save(["/tmp/test.wf"])
        
        assert rm.data_dir.exists()
        assert rm.recent_path.exists()


class TestRecentFileIntegration:
    """Integration tests for recent files with simulated GUI workflows."""

    @pytest.fixture
    def clean_recent_manager(self):
        """Get a fresh RecentFileManager with empty state."""
        rm = RecentFileManager()
        rm.save([])
        yield rm

    def test_gui_workflow_open_and_recent(self, clean_recent_manager):
        """
        Test the complete workflow:
        1. GUI opens a file
        2. New GUI instance loads recent list
        3. Open Recent selects a file
        """
        rm = clean_recent_manager
        
        # Step 1: GUI1 opens a file (simulating open_file_dialog)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.wf', delete=False) as f:
            test_file = f.name
            f.write("test")
        
        try:
            # This is what open_file_dialog() does
            abs_path = os.path.abspath(test_file)
            rm.add(abs_path)
            
            # Step 2: New GUI instance starts and loads recent list
            rm2 = RecentFileManager()
            recent_files = rm2.get_list()
            
            assert len(recent_files) > 0
            assert abs_path in recent_files[0]
            
            # Step 3: User selects from Open Recent (simulating _open_recent_file)
            rm2.move_to_top(test_file)
            result = rm2.get_list()
            
            assert abs_path in result[0]
        finally:
            try:
                os.unlink(test_file)
            except:
                pass

    def test_missing_file_removal_workflow(self, clean_recent_manager):
        """
        Test that missing files are automatically removed:
        1. Add a file to recent
        2. Delete the file
        3. Call get_list() - missing file should be removed
        """
        rm = clean_recent_manager
        
        # Create and add a file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.wf', delete=False) as f:
            test_file = f.name
            f.write("test")
        
        abs_path = os.path.abspath(test_file)
        rm.add(abs_path)
        
        # Verify it's there
        assert len(rm.load()) == 1
        
        # Delete the file
        os.unlink(test_file)
        
        # get_list should remove it
        result = rm.get_list()
        assert len(result) == 0
        
        # Verify it was persisted as removed
        loaded = rm.load()
        assert len(loaded) == 0

    def test_gui_startup_adds_to_recent(self, clean_recent_manager):
        """
        Test that launching GUI with a file path adds it to recent list.
        
        This simulates: wf gui /path/to/file.wf
        """
        rm = clean_recent_manager
        
        # Create a test workfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.wf', delete=False) as f:
            test_file = f.name
            f.write("test")
        
        try:
            abs_path = os.path.abspath(test_file)
            
            # Simulate GUI startup (what WorkflowApp.__init__ does now)
            rm.add(abs_path)
            
            # Verify file is in recent list
            recent = rm.get_list()
            assert len(recent) == 1
            assert abs_path in recent[0]
        finally:
            try:
                os.unlink(test_file)
            except:
                pass
