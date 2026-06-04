import os
import shutil
import traceback
import json
from threading import Timer
from datetime import datetime
import uno
import unohelper
from com.sun.star.util import XModifyListener, URL
from com.sun.star.task import XJob, XJobExecutor
from com.sun.star.frame import XDispatchProvider, XDispatch, FeatureStateEvent
from com.sun.star.lang import XInitialization
from com.sun.star.awt import XCallback
from pathlib import Path

LOG_FILE = Path.home() / "libreoffice_autosave_debug.log"
CONFIG_FILE = Path.home() / "libreoffice_autosave_config.json"

def is_debug_logging_enabled():
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                return config.get("debug_logging", False)
    except Exception:
        pass
    return False

def set_debug_logging_enabled(enabled):
    try:
        config = {}
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                try:
                    config = json.load(f)
                except Exception:
                    pass
        config["debug_logging"] = enabled
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
    except Exception:
        pass

def log_debug(msg):
    if not is_debug_logging_enabled():
        return
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass

log_debug("autosave.py module is being loaded by LibreOffice!")

g_status_listeners = []
g_listeners = {}

def notify_all_listeners():
    enabled = is_debug_logging_enabled()
    url = URL()
    url.Complete = "org.libreoffice.extensions.autosave.autosavejob:ToggleDebugLogging"
    for listener in list(g_status_listeners):
        try:
            event = FeatureStateEvent()
            event.FeatureURL = url
            event.Source = None
            event.IsEnabled = True
            event.Requery = False
            event.State = enabled
            listener.statusChanged(event)
        except Exception:
            try:
                g_status_listeners.remove(listener)
            except ValueError:
                pass

class SafeSaveCallback(unohelper.Base, XCallback):
    def __init__(self, listener):
        self.listener = listener

    def notify(self, data):
        try:
            self.listener._do_actual_save()
        except Exception as e:
            log_debug(f"Exception in SafeSaveCallback.notify: {e}\n{traceback.format_exc()}")

class AutoSaveListener(unohelper.Base, XModifyListener):
    def __init__(self, doc, delay_seconds=1.0):
        self.doc = doc
        self.delay = delay_seconds
        self.timer = None
        log_debug(f"AutoSaveListener initialized for document: {doc}")

    def modified(self, event):
        if self.timer:
            self.timer.cancel()
        
        self.timer = Timer(self.delay, self.execute_safe_save)
        self.timer.start()

    def execute_safe_save(self):
        try:
            log_debug("Timer expired, scheduling save on main thread via AsyncCallback...")
            ctx = uno.getComponentContext()
            smgr = ctx.ServiceManager
            async_cb = smgr.createInstanceWithContext("com.sun.star.awt.AsyncCallback", ctx)
            if async_cb:
                callback = SafeSaveCallback(self)
                async_cb.addCallback(callback, None)
                log_debug("Save scheduled successfully.")
            else:
                log_debug("Failed to create AsyncCallback service, falling back to direct save.")
                self._do_actual_save()
        except Exception as e:
            log_debug(f"Error scheduling safe save: {e}\n{traceback.format_exc()}")
            # Fallback
            try:
                self._do_actual_save()
            except Exception as e2:
                log_debug(f"Fallback save failed: {e2}")

    def _do_actual_save(self):
        try:
            log_debug("Timer expired, attempting save...")
            if self.doc.supportsService("com.sun.star.document.OfficeDocument"):
                if self.doc.hasLocation() and not self.doc.isReadonly():
                    file_url = self.doc.getURL()
                    log_debug(f"File has location: {file_url}")
                    
                    if file_url.startswith("file:///"):
                        system_path = uno.fileUrlToSystemPath(file_url)
                        bak_path = os.path.join(os.path.dirname(system_path), f".{os.path.basename(system_path)}.bak")
                        try:
                            if os.path.exists(system_path):
                                shutil.copy2(system_path, bak_path)
                                log_debug(f"Created backup at {bak_path}")
                        except Exception as e:
                            log_debug(f"Backup failed: {e}")
                    
                    self.doc.store()
                    log_debug("Document successfully saved.")
                else:
                    log_debug("Document is readonly or has no location (not saved yet).")
        except Exception as e:
            log_debug(f"Auto-save exception: {e}\n{traceback.format_exc()}")

    def disposing(self, event):
        if self.timer:
            self.timer.cancel()
        
        # Remove from g_listeners dictionary to prevent leaks
        doc = getattr(event, "Source", self.doc)
        try:
            if doc in g_listeners:
                del g_listeners[doc]
                log_debug("Successfully removed document from g_listeners on dispose.")
            elif self.doc in g_listeners:
                del g_listeners[self.doc]
                log_debug("Successfully removed self.doc from g_listeners on dispose.")
        except Exception as e:
            log_debug(f"Error removing document from g_listeners: {e}")
            
        log_debug("Listener disposed.")

class AutoSaveJob(unohelper.Base, XJob, XJobExecutor, XDispatchProvider, XDispatch, XInitialization):
    def __init__(self, ctx=None):
        self.ctx = ctx
        self.frame = None
        log_debug("AutoSaveJob instantiated!")

    # XInitialization
    def initialize(self, args):
        log_debug(f"AutoSaveJob initialize() called with args: {args}")
        if len(args) > 0:
            self.frame = args[0]

    # XJob & XJobExecutor
    def execute(self, arguments):
        log_debug(f"AutoSaveJob execute() called with args: {arguments}")
        self._attach_listener(arguments)
        return ()

    def trigger(self, args):
        log_debug(f"AutoSaveJob trigger() called with args: {args}")
        self._attach_listener()

    # XDispatchProvider
    def queryDispatch(self, url, targetFrameName, searchFlags):
        log_debug(f"queryDispatch called for URL: {url.Complete}")
        if url.Complete.startswith("org.libreoffice.extensions.autosave.autosavejob:"):
            return self
        return None

    def queryDispatches(self, requests):
        return tuple(self.queryDispatch(r.URL, r.FrameName, r.SearchFlags) for r in requests)

    # XDispatch
    def dispatch(self, url, arguments):
        log_debug(f"dispatch called for URL: {url.Complete}")
        if url.Complete.endswith("ToggleDebugLogging"):
            current = is_debug_logging_enabled()
            set_debug_logging_enabled(not current)
            log_debug(f"Toggled debug logging to: {not current}")
            notify_all_listeners()

    def addStatusListener(self, listener, url):
        log_debug(f"addStatusListener called for URL: {url.Complete}")
        if url.Complete.endswith("ToggleDebugLogging"):
            if listener not in g_status_listeners:
                g_status_listeners.append(listener)
            try:
                event = FeatureStateEvent()
                event.FeatureURL = url
                event.Source = self
                event.IsEnabled = True
                event.Requery = False
                event.State = is_debug_logging_enabled()
                listener.statusChanged(event)
            except Exception as e:
                log_debug(f"Error in addStatusListener initial notify: {e}")

    def removeStatusListener(self, listener, url):
        log_debug(f"removeStatusListener called for URL: {url.Complete}")
        if listener in g_status_listeners:
            g_status_listeners.remove(listener)

    def _attach_listener(self, arguments=None):
        try:
            doc = None
            if arguments:
                for arg in arguments:
                    if hasattr(arg, "Name") and arg.Name == "Model":
                        doc = arg.Value
                        break
            
            if not doc:
                ctx = uno.getComponentContext()
                smgr = ctx.ServiceManager
                desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
                doc = desktop.getCurrentComponent()
            
            if doc:
                if doc in g_listeners:
                    log_debug("Listener already attached to this document.")
                    return
                listener = AutoSaveListener(doc, delay_seconds=1.0)
                doc.addModifyListener(listener)
                g_listeners[doc] = listener
                log_debug("Successfully attached listener to current document.")
            else:
                log_debug("No active document found.")
        except Exception as e:
            log_debug(f"Error in AutoSaveJob attach: {e}\n{traceback.format_exc()}")

g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    AutoSaveJob,
    "org.libreoffice.extensions.autosave.AutoSaveJob",
    ("com.sun.star.task.Job", "com.sun.star.frame.ProtocolHandler"),
)
