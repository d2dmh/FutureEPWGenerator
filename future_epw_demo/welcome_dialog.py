from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class WelcomeDialog(QDialog):
    """First-launch welcome with Create Project / Open Project actions."""

    def __init__(self, translator, parent=None):
        super().__init__(parent)
        self.tr = translator
        self.requested_action = "create"
        self.setWindowTitle(self.tr.text("welcome.title"))
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(18)

        title = QLabel(self.tr.text("welcome.title"))
        title.setObjectName("PageTitle")
        body = QLabel(self.tr.text("welcome.body"))
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(title)
        layout.addWidget(body)

        actions = QHBoxLayout()
        actions.addStretch()
        create = QPushButton(self.tr.text("welcome.create"))
        open_btn = QPushButton(self.tr.text("welcome.open"))
        create.setDefault(True)
        create.clicked.connect(self._create)
        open_btn.clicked.connect(self._open)
        actions.addWidget(open_btn)
        actions.addWidget(create)
        layout.addLayout(actions)

    def _create(self) -> None:
        self.requested_action = "create"
        self.accept()

    def _open(self) -> None:
        self.requested_action = "open"
        self.accept()
