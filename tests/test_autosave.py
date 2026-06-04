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
class MockXDispatchProvider: pass
class MockXDispatch: pass
class MockXInitialization: pass
class MockFeatureStateEvent: pass
class MockURL: pass
class MockXCallback: pass

mock_util = MagicMock()
mock_util.XModifyListener = MockListener
mock_util.URL = MockURL
sys.modules['com.sun.star.util'] = mock_util

mock_task = MagicMock()
mock_task.XJob = MockXJob
mock_task.XJobExecutor = MockXJobExecutor
sys.modules['com.sun.star.task'] = mock_task

mock_frame = MagicMock()
mock_frame.XDispatchProvider = MockXDispatchProvider
mock_frame.XDispatch = MockXDispatch
mock_frame.FeatureStateEvent = MockFeatureStateEvent
sys.modules['com.sun.star.frame'] = mock_frame

mock_lang = MagicMock()
mock_lang.XInitialization = MockXInitialization
sys.modules['com.sun.star.lang'] = mock_lang

mock_awt = MagicMock()
mock_awt.XCallback = MockXCallback
sys.modules['com.sun.star.awt'] = mock_awt

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
    
    # Mock context and smgr for AsyncCallback
    mock_ctx = MagicMock()
    autosave.uno.getComponentContext.return_value = mock_ctx
    mock_smgr = MagicMock()
    mock_ctx.ServiceManager = mock_smgr
    mock_async_cb = MagicMock()
    mock_async_cb.addCallback.side_effect = lambda cb, data: cb.notify(data)
    mock_smgr.createInstanceWithContext.return_value = mock_async_cb
    
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
    
    # Mock context and smgr for AsyncCallback
    mock_ctx = MagicMock()
    autosave.uno.getComponentContext.return_value = mock_ctx
    mock_smgr = MagicMock()
    mock_ctx.ServiceManager = mock_smgr
    mock_async_cb = MagicMock()
    mock_async_cb.addCallback.side_effect = lambda cb, data: cb.notify(data)
    mock_smgr.createInstanceWithContext.return_value = mock_async_cb
    
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

def test_autosave_job_execution_with_model():
    job = AutoSaveJob()
    
    # Create a mock NamedValue for the Model argument
    mock_arg = MagicMock()
    mock_arg.Name = "Model"
    mock_doc = MagicMock()
    mock_arg.Value = mock_doc
    
    # Execute the job with the Model argument
    job.execute((mock_arg,))
    
    # The listener should be created and attached to the passed mock_doc
    assert mock_doc in autosave.g_listeners
    mock_doc.addModifyListener.assert_called_once()

def test_disposing_cleanup():
    mock_doc = MagicMock()
    listener = AutoSaveListener(mock_doc)
    
    # Put listener in g_listeners
    autosave.g_listeners[mock_doc] = listener
    assert mock_doc in autosave.g_listeners
    
    # Trigger disposing
    mock_event = MagicMock()
    mock_event.Source = mock_doc
    listener.disposing(mock_event)
    
    # The document should be removed from g_listeners
    assert mock_doc not in autosave.g_listeners

def test_debug_logging_configuration(tmp_path):
    # Temporarily redirect CONFIG_FILE to a temp file
    config_file = tmp_path / "autosave_config.json"
    with patch('src.autosave.CONFIG_FILE', config_file):
        # Default should be False
        assert not autosave.is_debug_logging_enabled()
        
        # Enabling should set it to True
        autosave.set_debug_logging_enabled(True)
        assert autosave.is_debug_logging_enabled()
        
        # Disabling should set it to False
        autosave.set_debug_logging_enabled(False)
        assert not autosave.is_debug_logging_enabled()

def test_log_debug_only_when_enabled(tmp_path):
    config_file = tmp_path / "autosave_config.json"
    log_file = tmp_path / "autosave_debug.log"
    
    with patch('src.autosave.CONFIG_FILE', config_file), patch('src.autosave.LOG_FILE', log_file):
        # By default (disabled), log_debug should not write
        autosave.log_debug("test message 1")
        assert not log_file.exists()
        
        # When enabled, log_debug should write
        autosave.set_debug_logging_enabled(True)
        autosave.log_debug("test message 2")
        assert log_file.exists()
        with open(log_file, "r") as f:
            content = f.read()
            assert "test message 2" in content

def test_protocol_handler_dispatch(tmp_path):
    config_file = tmp_path / "autosave_config.json"
    job = AutoSaveJob()
    
    with patch('src.autosave.CONFIG_FILE', config_file):
        # Set to False initially
        autosave.set_debug_logging_enabled(False)
        
        # Query dispatch
        mock_url = MagicMock()
        mock_url.Complete = "org.libreoffice.extensions.autosave.autosavejob:ToggleDebugLogging"
        dispatcher = job.queryDispatch(mock_url, "_self", 0)
        assert dispatcher is job
        
        # Query dispatch with invalid protocol
        invalid_url = MagicMock()
        invalid_url.Complete = "invalid.protocol:ToggleDebugLogging"
        assert job.queryDispatch(invalid_url, "_self", 0) is None
        
        # Query dispatches
        req = MagicMock()
        req.URL = mock_url
        req.FrameName = "_self"
        req.SearchFlags = 0
        dispatchers = job.queryDispatches((req,))
        assert dispatchers == (job,)
        
        # Test dispatch
        job.dispatch(mock_url, ())
        assert autosave.is_debug_logging_enabled()
        
        # Test status listener
        mock_listener = MagicMock()
        job.addStatusListener(mock_listener, mock_url)
        assert mock_listener in autosave.g_status_listeners
        
        # Verifying statusChanged was called with initial state (True)
        mock_listener.statusChanged.assert_called_once()
        event = mock_listener.statusChanged.call_args[0][0]
        assert event.State is True
        
        # Dispatching again should toggle to False and notify
        mock_listener.statusChanged.reset_mock()
        job.dispatch(mock_url, ())
        assert not autosave.is_debug_logging_enabled()
        mock_listener.statusChanged.assert_called_once()
        event = mock_listener.statusChanged.call_args[0][0]
        assert event.State is False
        
        # Remove listener
        job.removeStatusListener(mock_listener, mock_url)
        assert mock_listener not in autosave.g_status_listeners

