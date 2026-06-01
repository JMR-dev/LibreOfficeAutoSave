import os
import shutil
import traceback
from threading import Timer
from datetime import datetime
import uno
import unohelper
from com.sun.star.util import XModifyListener
from com.sun.star.task import XJob, XJobExecutor

LOG_FILE = "C:\\Users\\jasonross\\workspace\\LibreOfficeAutoSave\\autosave_debug.log"

def log_debug(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass

log_debug("autosave.py module is being loaded by LibreOffice!")

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
        log_debug("Listener disposed.")

g_listeners = {}

class AutoSaveJob(unohelper.Base, XJob, XJobExecutor):
    def __init__(self, ctx=None):
        self.ctx = ctx
        log_debug("AutoSaveJob instantiated!")

    def execute(self, arguments):
        log_debug(f"AutoSaveJob execute() called with args: {arguments}")
        self._attach_listener()
        return ()

    def trigger(self, args):
        log_debug(f"AutoSaveJob trigger() called with args: {args}")
        self._attach_listener()

    def _attach_listener(self):
        try:
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
    ("com.sun.star.task.Job",),
)
