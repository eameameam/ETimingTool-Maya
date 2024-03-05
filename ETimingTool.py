import maya.cmds as cmds
import maya.OpenMayaUI as omui
from PySide2 import QtCore, QtWidgets, QtGui
from shiboken2 import wrapInstance
from contextlib import contextmanager
import random
import os

eTimingTool_window = None

icon_folder = os.path.join(cmds.internalVar(userPrefDir=True), "icons", "ETimingTool")

def maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)

class ETimingToolWindow(QtWidgets.QDialog):
    def __init__(self, parent=maya_main_window()):
        super(ETimingToolWindow, self).__init__(parent)
        
        self.setWindowTitle("ETimingTool")
        self.setMinimumWidth(250)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

        self.create_widgets()
        self.create_layouts()
        
    def create_widgets(self):
        self.frame = QtWidgets.QWidget(self)
        self.frame.setStyleSheet("""
            QWidget {
                background-color: rgba(10, 10, 10, 240);
                border-radius: 10px;
                min-width: 250px;
                min-height: 150px;
            }
        """)

        self.threshold_label = QtWidgets.QLabel("Movement Threshold:")
        self.threshold_label.setStyleSheet("color: grey; font-weight: bold;")
        self.threshold_spinbox = QtWidgets.QDoubleSpinBox()
        self.threshold_spinbox.setRange(0.01, 10.0)
        self.threshold_spinbox.setValue(1)
        self.threshold_spinbox.setStyleSheet("background-color: grey; color: black;")
        self.analyze_button = self.create_button("", "Analyze timing", self.on_analyze_clicked, icon_path=os.path.join(icon_folder, "analyze.png"))
        self.clear_markers_button = self.create_button("", "Clear all timing markers", self.clear_markers, icon_path=os.path.join(icon_folder, "clearMarkers.png"))

        self.close_button = QtWidgets.QPushButton()
        self.close_button.setIcon(QtGui.QIcon(os.path.join(icon_folder, "closeButton.png")))
        self.close_button.setIconSize(QtCore.QSize(20, 20))
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(10, 10, 10, 0);
                border: none;
            }
            QPushButton::hover {
                background-color: rgba(20, 20, 20, 240);
            }
            QPushButton:pressed {
                background-color: rgba(0, 0, 0, 240);
            }
        """)
        self.close_button.setFixedSize(20, 20)
        self.close_button.clicked.connect(self.close)

    def create_button(self, text, tooltip, callback, icon_path=None):
        button = QtWidgets.QPushButton(text)
        button.setToolTip(tooltip)
        tooltip_style = """
            QToolTip {
                background-color: rgb(30, 30, 30);
                color: rgb(200, 200, 200);
                border: none;
            }
        """
        self.setStyleSheet(tooltip_style)
        if icon_path:
            button.setIcon(QtGui.QIcon(icon_path))
            button.setIconSize(QtCore.QSize(200, 30)) 
            button.setFixedSize(230, 30)

        button.clicked.connect(callback)
        button.setStyleSheet("""
            QPushButton {
                background-color: rgba(30, 30, 30, 240);
                border-radius: 5px;
            }
            QPushButton::hover {
                background-color: rgba(20, 20, 20, 240);
            }
            QPushButton:pressed {
                background-color: rgba(0, 0, 0, 240);
            }
            QPushButton[active="true"] {
                background-color: rgba(160, 160, 160, 240);
            }
            """)

        return button

    def mousePressEvent(self, event):
        self.mouseClickPosition = event.globalPos() - self.pos()
        super(ETimingToolWindow, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.mouseClickPosition:
            self.move(event.globalPos() - self.mouseClickPosition)
        super(ETimingToolWindow, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.mouseClickPosition = None
        super(ETimingToolWindow, self).mouseReleaseEvent(event)

    def create_layouts(self):
        main_layout = QtWidgets.QVBoxLayout(self.frame)
        title_bar_layout = QtWidgets.QHBoxLayout()
        title_bar_layout.addWidget(self.threshold_label)
        title_bar_layout.addStretch()
        title_bar_layout.addWidget(self.close_button)

        main_layout.addLayout(title_bar_layout)
        main_layout.addWidget(self.threshold_spinbox)
        main_layout.addWidget(self.analyze_button)
        main_layout.addWidget(self.clear_markers_button)
        self.setLayout(main_layout)

    def on_analyze_clicked(self):
        threshold = self.threshold_spinbox.value()
        self.analyze_animation(threshold)

    def clear_markers(self):
        bookmarks = cmds.ls(type='timeSliderBookmark')
        if bookmarks:
            with undo_chunk():
                cmds.delete(bookmarks)
                
    def analyze_animation(self, threshold):
        if not cmds.pluginInfo("timeSliderBookmark", query=True, loaded=True):
            cmds.loadPlugin("timeSliderBookmark", quiet=True)

        start_time = cmds.playbackOptions(q=True, minTime=True)
        end_time = cmds.playbackOptions(q=True, maxTime=True)
        controllers = cmds.ls(selection=True, type='transform')

        if not controllers:
            cmds.warning("Please select at least one control.")
            return

        stagnant_periods = []
        is_stagnant = False

        with undo_chunk():
            for time in range(int(start_time), int(end_time) + 1):
                cmds.currentTime(time)
                significant_change = False

                for ctrl in controllers:
                    for attr in ('translateX', 'translateY', 'translateZ'):
                        if time == int(start_time):
                            continue
                        current_val = cmds.getAttr(f"{ctrl}.{attr}", time=time)
                        prev_val = cmds.getAttr(f"{ctrl}.{attr}", time=time-1)
                        if abs(current_val - prev_val) > threshold:
                            significant_change = True
                            break

                if significant_change:
                    if is_stagnant:
                        stagnant_periods.append((stagnant_start, time - 1))
                        is_stagnant = False
                else:
                    if not is_stagnant:
                        stagnant_start = time
                        is_stagnant = True

            if is_stagnant:
                stagnant_periods.append((stagnant_start, int(end_time)))

            self.clear_markers()

            for start, end in stagnant_periods:
                bookmark_node = cmds.createNode('timeSliderBookmark', name=f"Stagnant_{start}_{end}")
                cmds.setAttr(f"{bookmark_node}.color", random.uniform(0.3, 1.0), random.uniform(0.3, 1.0), random.uniform(0.3, 1.0), type='double3')
                cmds.setAttr(f"{bookmark_node}.timeRangeStart", start)
                cmds.setAttr(f"{bookmark_node}.timeRangeStop", end)

@contextmanager
def undo_chunk():
    try:
        cmds.undoInfo(openChunk=True)
        yield
    finally:
        cmds.undoInfo(closeChunk=True)

def create_eTimingTool_window():
    global eTimingTool_window
    if eTimingTool_window is not None:
        eTimingTool_window.close()
        eTimingTool_window = None
    eTimingTool_window = ETimingToolWindow()
    eTimingTool_window.show()

create_eTimingTool_window()