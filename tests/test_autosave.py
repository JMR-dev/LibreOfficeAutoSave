import sys
import os
import time
from unittest.mock import MagicMock, patch

# Add the project root to sys.path so we can import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock the uno and unohelper modules before importing our module
sys.modules['uno'] = MagicMock()

class MockBase: pass
mock_unohelper = MagicMock()
mock_unohelper.Base = MockBase
sys.modules['unohelper'] = mock_unohelper

class MockListener: pass
class MockXJob: pass
class MockXJobExecutor: pass

mock_util = MagicMock()
mock_util.XModifyListener = MockListener
sys.modules['com.sun.star.util'] = mock_util

mock_task = MagicMock()
mock_task.XJob = MockXJob
mock_task.XJobExecutor = MockXJobExecutor
sys.modules['com.sun.star.task'] = mock_task

# Now we can safely import our module
import src.autosave as autosave
from src.autosave import AutoSaveListener, AutoSaveJob

def setup_function():
    # Clear the global listeners dictionary before each test
    autosave.g_listeners.clear()

def test_debounce_timer():
    mock_doc = MagicMock()
    listener = AutoSaveListener(mock_doc, delay_seconds=0.1)
    
    # Simulate multiple rapid modifications
    listener.modified(None)
    first_timer = listener.timer
    
    listener.modified(None)
    second_timer = listener.timer
    
    # The first timer should be cancelled, the second should be active
    assert first_timer is not second_timer
    
    # Ensure execute_safe_save has not executed synchronously
    mock_doc.store.assert_not_called()

@patch('src.autosave.os.path.exists')
@patch('src.autosave.shutil.copy2')
def test_execute_safe_save_success(mock_copy2, mock_exists):
    mock_doc = MagicMock()
    mock_doc.supportsService.return_value = True
    mock_doc.hasLocation.return_value = True
    mock_doc.isReadonly.return_value = False
    mock_doc.getURL.return_value = "file:///dummy/path/test.odt"
    
    # Mock uno.fileUrlToSystemPath to just return a string
    autosave.uno.fileUrlToSystemPath.return_value = "/dummy/path/test.odt"
    mock_exists.return_value = True
    
    listener = AutoSaveListener(mock_doc, delay_seconds=0.1)
    listener.execute_safe_save()
    
    # Assert copy2 was called to create the backup
    mock_copy2.assert_called_once()
    # Assert store() was called to save the document
    mock_doc.store.assert_called_once()

def test_execute_safe_save_no_location():
    mock_doc = MagicMock()
    mock_doc.supportsService.return_value = True
    mock_doc.hasLocation.return_value = False # Document not saved yet
    
    listener = AutoSaveListener(mock_doc)
    listener.execute_safe_save()
    
    # store() should NOT be called
    mock_doc.store.assert_not_called()

def test_autosave_job_execution():
    job = AutoSaveJob()
    
    # Mock context and document
    mock_ctx = MagicMock()
    autosave.uno.getComponentContext.return_value = mock_ctx
    
    mock_smgr = MagicMock()
    mock_ctx.ServiceManager = mock_smgr
    
    mock_desktop = MagicMock()
    mock_smgr.createInstanceWithContext.return_value = mock_desktop
    
    mock_doc = MagicMock()
    mock_desktop.getCurrentComponent.return_value = mock_doc
    
    # Execute the job
    job.execute(())
    
    # The listener should be created and attached
    assert mock_doc in autosave.g_listeners
    mock_doc.addModifyListener.assert_called_once()

    # Re-executing should not attach a duplicate listener
    job.execute(())
    assert mock_doc.addModifyListener.call_count == 1
