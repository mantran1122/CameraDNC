# coding=utf-8
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot


class Bridge(QObject):
    """QWebChannel bridge — Python signals exposed to JS, JS slots calling Python."""

    # Python → JS
    demo_started = pyqtSignal(str)        # module_path
    demo_stopped = pyqtSignal(str)        # module_path
    demo_error   = pyqtSignal(str, str)   # module_path, error_message
    app_status   = pyqtSignal(str, str)   # message, color_hex

    def __init__(self, launcher, parent=None):
        super().__init__(parent)
        self._launcher = launcher

    # JS → Python
    @pyqtSlot(str)
    def launch(self, module_path):
        self._launcher.launch(module_path)

    @pyqtSlot()
    def open_folder(self):
        self._launcher._open_folder()

    @pyqtSlot()
    def quit_app(self):
        self._launcher.close()
