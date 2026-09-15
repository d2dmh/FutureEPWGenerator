from __future__ import annotations

from PySide6.QtCore import Qt

from .i18n import Translator, bind_text
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class NavStepButton(QPushButton):
    """Scientific workflow step with restrained active accent and state text."""

    def __init__(self, number: int, title: str):
        super().__init__()
        self.setObjectName("NavStepButton")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(58)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 8, 6)
        layout.setSpacing(10)

        self.accent = QFrame()
        self.accent.setObjectName("NavAccent")
        self.accent.setFixedWidth(3)
        self.accent.setVisible(False)

        self.number_label = QLabel(str(number))
        self.number_label.setObjectName("NavNumber")
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_label.setFixedSize(23, 23)

        text_column = QWidget()
        text_column.setObjectName("NavTextColumn")
        text_layout = QVBoxLayout(text_column)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("NavTitle")
        self.status_label = QLabel("Pending")
        self.status_label.setObjectName("NavStatusText")

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.status_label)

        layout.addWidget(self.accent)
        layout.addWidget(self.number_label)
        layout.addWidget(text_column, 1)

    def set_step_state(self, status: str, *, active: bool = False, kind: str = "pending") -> None:
        self.setChecked(active)
        self.accent.setVisible(active)
        self.status_label.setText(status)
        self.status_label.setProperty("statusKind", kind)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)


def card(title: str | None = None, *, translator: Translator | None = None, title_key: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(17, 15, 17, 15)
    layout.setSpacing(11)
    if title:
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        if translator is not None and title_key:
            bind_text(label, title_key, translator)
        layout.addWidget(label)
    return frame, layout


def data_panel(title: str, subtitle: str = "", *, translator: Translator | None = None, title_key: str | None = None, subtitle_key: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("DataPanel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)
    title_label = QLabel(title)
    title_label.setObjectName("DataPanelTitle")
    if translator is not None and title_key:
        bind_text(title_label, title_key, translator)
    layout.addWidget(title_label)
    if subtitle:
        caption = QLabel(subtitle)
        caption.setObjectName("DataPanelSubtitle")
        if translator is not None and subtitle_key:
            bind_text(caption, subtitle_key, translator)
        caption.setWordWrap(True)
        layout.addWidget(caption)
    return frame, layout


def page_header(title: str, subtitle: str, *, translator: Translator | None = None, title_key: str | None = None, subtitle_key: str | None = None) -> tuple[QLabel, QLabel]:
    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("PageSubtitle")
    if translator is not None and title_key:
        bind_text(title_label, title_key, translator)
    if translator is not None and subtitle_key:
        bind_text(subtitle_label, subtitle_key, translator)
    return title_label, subtitle_label


def metadata_block(label: str, value: str, value_object: str = "MetaValue", *, tile: bool = False) -> QFrame:
    block = QFrame()
    block.setObjectName("SummaryTile" if tile else "MetadataBlock")
    layout = QVBoxLayout(block)
    layout.setContentsMargins(10 if tile else 0, 8 if tile else 0, 10 if tile else 0, 8 if tile else 0)
    layout.setSpacing(2)
    key = QLabel(label)
    key.setObjectName("MetaLabel")
    val = QLabel(value)
    val.setObjectName(value_object)
    layout.addWidget(key)
    layout.addWidget(val)
    return block


def metric_cell(kicker: str, value: str, detail: str = "", *, mono: bool = False) -> QFrame:
    cell = QFrame()
    cell.setObjectName("MetricCell")
    layout = QVBoxLayout(cell)
    layout.setContentsMargins(12, 9, 12, 9)
    layout.setSpacing(2)
    k = QLabel(kicker.upper())
    k.setObjectName("MetricKicker")
    v = QLabel(value)
    v.setObjectName("MonoValue" if mono else "MetricValue")
    layout.addWidget(k)
    layout.addWidget(v)
    if detail:
        d = QLabel(detail)
        d.setObjectName("MetricDetail")
        d.setWordWrap(True)
        layout.addWidget(d)
    return cell


def research_strip(items: list[tuple[str, str, str]]) -> QFrame:
    frame = QFrame()
    frame.setObjectName("ResearchStrip")
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    for kicker, value, detail in items:
        layout.addWidget(metric_cell(kicker, value, detail), 1)
    return frame


def status_pill(text: str, kind: str = "info") -> QLabel:
    label = QLabel(text)
    label.setObjectName("StatusPill")
    label.setProperty("statusKind", kind)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


def pipeline_node(stage: str, title: str, detail: str, status: str, kind: str = "complete") -> QFrame:
    node = QFrame()
    node.setObjectName("PipelineNode")
    layout = QHBoxLayout(node)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(12)

    stage_label = QLabel(stage)
    stage_label.setObjectName("PipelineStage")
    stage_label.setFixedWidth(66)
    layout.addWidget(stage_label)

    text = QWidget()
    text_layout = QVBoxLayout(text)
    text_layout.setContentsMargins(0, 0, 0, 0)
    text_layout.setSpacing(2)
    title_label = QLabel(title)
    title_label.setObjectName("PipelineTitle")
    detail_label = QLabel(detail)
    detail_label.setObjectName("PipelineDetail")
    detail_label.setWordWrap(True)
    text_layout.addWidget(title_label)
    text_layout.addWidget(detail_label)
    layout.addWidget(text, 1)
    layout.addWidget(status_pill(status, kind))
    return node
