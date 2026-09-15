from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from .app_settings import AppSettings
from .i18n import Translator, bind_text, retranslate_tree


class SettingsDialog(QDialog):
    """Application preferences only; no research project state is modified."""

    def __init__(self, settings: AppSettings, translator: Translator, parent=None):
        super().__init__(parent)
        self._original = settings
        self._translator = translator
        self.settings = settings
        self.setModal(True)
        self.resize(520, 360)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        self.title_label = QLabel("Settings")
        self.title_label.setObjectName("PageTitle")
        bind_text(self.title_label, "settings.title", translator)
        root.addWidget(self.title_label)

        general = QGroupBox("General")
        bind_text(general, "settings.general", translator)
        grid = QGridLayout(general)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)

        language_label = QLabel("Language")
        bind_text(language_label, "settings.language", translator)
        self.language = QComboBox()
        self.language.addItem("English", "en")
        self.language.addItem("简体中文", "zh_CN")
        self.language.setCurrentIndex(max(0, self.language.findData(settings.language)))
        grid.addWidget(language_label, 0, 0)
        grid.addWidget(self.language, 0, 1)

        text_size_label = QLabel("Text size")
        bind_text(text_size_label, "settings.text_size", translator)
        self.text_scale = QComboBox()
        self.text_scale.addItem("Small", "small")
        self.text_scale.addItem("Standard", "standard")
        self.text_scale.addItem("Large", "large")
        self.text_scale.setCurrentIndex(max(0, self.text_scale.findData(settings.text_scale)))
        grid.addWidget(text_size_label, 1, 0)
        grid.addWidget(self.text_scale, 1, 1)

        self.reopen_last = QCheckBox("Reopen last project automatically")
        bind_text(self.reopen_last, "settings.reopen_last", translator)
        self.reopen_last.setChecked(settings.reopen_last_project)
        grid.addWidget(self.reopen_last, 2, 0, 1, 2)
        root.addWidget(general)

        display = QGroupBox("Display")
        bind_text(display, "settings.display", translator)
        display_layout = QVBoxLayout(display)
        self.show_log = QCheckBox("Show detailed backend log by default")
        bind_text(self.show_log, "settings.show_log", translator)
        self.show_log.setChecked(settings.show_detailed_log)
        display_layout.addWidget(self.show_log)
        root.addWidget(display)
        root.addStretch()

        actions = QHBoxLayout()
        self.restore_btn = QPushButton("Restore defaults")
        bind_text(self.restore_btn, "common.restore_defaults", translator)
        self.cancel_btn = QPushButton("Cancel")
        bind_text(self.cancel_btn, "common.cancel", translator)
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setObjectName("PrimaryButton")
        bind_text(self.apply_btn, "common.apply", translator)
        self.restore_btn.clicked.connect(self._restore_defaults)
        self.cancel_btn.clicked.connect(self.reject)
        self.apply_btn.clicked.connect(self._apply)
        actions.addWidget(self.restore_btn)
        actions.addStretch()
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.apply_btn)
        root.addLayout(actions)
        self.retranslate_ui()

    def _restore_defaults(self) -> None:
        defaults = AppSettings()
        self.language.setCurrentIndex(max(0, self.language.findData(defaults.language)))
        self.text_scale.setCurrentIndex(max(0, self.text_scale.findData(defaults.text_scale)))
        self.reopen_last.setChecked(defaults.reopen_last_project)
        self.show_log.setChecked(defaults.show_detailed_log)

    def _apply(self) -> None:
        self.settings = replace(
            self._original,
            language=str(self.language.currentData()),
            text_scale=str(self.text_scale.currentData()),
            reopen_last_project=self.reopen_last.isChecked(),
            show_detailed_log=self.show_log.isChecked(),
        )
        self.accept()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self._translator.text("settings.title"))
        retranslate_tree(self, self._translator)
        # Combo-box display labels are not child text widgets.
        idx = self.language.currentIndex()
        self.language.setItemText(0, self._translator.text("settings.language.en"))
        self.language.setItemText(1, self._translator.text("settings.language.zh_CN"))
        self.language.setCurrentIndex(idx)
        idx = self.text_scale.currentIndex()
        self.text_scale.setItemText(0, self._translator.text("settings.text_size.small"))
        self.text_scale.setItemText(1, self._translator.text("settings.text_size.standard"))
        self.text_scale.setItemText(2, self._translator.text("settings.text_size.large"))
        self.text_scale.setCurrentIndex(idx)
