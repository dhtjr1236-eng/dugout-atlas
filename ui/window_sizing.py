"""Compact default windows without losing access to oversized content."""
from PyQt6.QtWidgets import QScrollArea


def compact_dimensions(width, height, available_width, available_height):
    return (max(1, min(round(width * .9), available_width - 32)),
            max(1, min(round(height * .9), available_height - 64)))


def compact_main_window(window, width, height):
    # A scroll viewport prevents child minimumSizeHints from enlarging the window
    # beyond the screen on small monitors / high DPI / large-font settings.
    content = window.takeCentralWidget()
    scroll = QScrollArea(window)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setWidget(content)
    window.setCentralWidget(scroll)
    screen = window.screen()
    if screen:
        area = screen.availableGeometry()
        size = compact_dimensions(width, height, area.width(), area.height())
    else:
        size = (round(width * .9), round(height * .9))
    window.resize(*size)
