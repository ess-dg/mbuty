from qtpy.QtWidgets import QApplication, QLabel
import sys

app = QApplication(sys.argv)
label = QLabel("hello world")
label.resize(300, 100)
label.show()
sys.exit(app.exec())