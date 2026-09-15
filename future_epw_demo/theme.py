APP_STYLE = """
QWidget {
    color: #142033;
    font-family: 'Segoe UI', 'Microsoft YaHei', Arial;
    font-size: 13px;
}
QLabel { background: transparent; }
QMainWindow, QFrame#AppSurface, QWidget#BodySurface, QWidget#ContentSurface {
    background: #F3F6FA;
}
QFrame#TopBar {
    background: #FFFFFF;
    border: 0;
    border-bottom: 1px solid #DDE4ED;
}
QWidget#BrandColumn { background: transparent; }
QFrame#BottomBar {
    background: #FBFCFE;
    border: 0;
    border-top: 1px solid #DDE4ED;
}
QFrame#Sidebar {
    background: #FBFCFE;
    border-right: 1px solid #DDE4ED;
}
QFrame#Card {
    background: #FFFFFF;
    border: 1px solid #DDE4ED;
    border-radius: 10px;
}
QFrame#ActionBar {
    background: #F3F6FA;
    border: 0;
    border-top: 1px solid #DCE3EC;
}
QFrame#MetadataBlock { background: transparent; border: 0; }
QFrame#WeatherMetadataPanel {
    background: #F8FAFD;
    border: 1px solid #E1E7EF;
    border-radius: 8px;
}
QFrame#WeatherMetric {
    background: transparent;
    border: 0;
    border-right: 1px solid #E6EBF2;
    border-bottom: 1px solid #E6EBF2;
    padding: 0;
}
QFrame#ProjectSummary {
    background: #FFFFFF;
    border: 1px solid #DDE4ED;
    border-radius: 10px;
}
QFrame#MetricCell {
    background: transparent;
    border: 0;
    border-right: 1px solid #E3E8EF;
}
QFrame#ScientificNote {
    background: #EDF5FF;
    border: 1px solid #D4E5FB;
    border-left: 3px solid #2B6DEB;
    border-radius: 7px;
}
QFrame#NavAccent {
    background: #2B6DEB;
    border: 0;
    border-radius: 1px;
}
QLabel#BrandName { font-size: 16px; font-weight: 700; color: #0B1F33; }
QLabel#ResearchTag { color: #728197; font-size: 10px; letter-spacing: 0.3px; }
QLabel#ModeChip {
    color: #1F5DB8;
    background: #EEF5FF;
    border: 1px solid #D6E6FB;
    border-radius: 11px;
    padding: 3px 8px;
    font-size: 10px;
    font-weight: 600;
}
QLabel#ProjectChip {
    color: #344054;
    background: #F7F9FC;
    border: 1px solid #DDE4ED;
    border-radius: 14px;
    padding: 5px 11px;
}
QLabel#PageTitle { font-size: 25px; font-weight: 700; color: #0B1F33; }
QLabel#PageSubtitle { color: #68788E; font-size: 12px; }
QLabel#SectionTitle { font-size: 14px; font-weight: 700; color: #12243A; }
QLabel#SectionEyebrow { color: #718096; font-size: 10px; font-weight: 700; letter-spacing: 0.7px; }
QLabel#FieldLabel { color: #526174; font-weight: 600; }
QLabel#MetaLabel { color: #7B899B; font-size: 10px; }
QLabel#MetaValue { color: #142033; font-size: 12px; font-weight: 600; }
QLabel#MetricKicker { color: #8290A3; font-size: 9px; font-weight: 700; letter-spacing: 0.8px; }
QLabel#MetricValue { color: #102A43; font-size: 16px; font-weight: 700; }
QLabel#MetricDetail { color: #718096; font-size: 10px; }
QLabel#ScientificNoteTitle { color: #245EA8; font-size: 10px; font-weight: 700; }
QLabel#ScientificNoteText { color: #51647C; font-size: 11px; }
QLabel#Muted { color: #718096; }
QLabel#Success { color: #0F7A50; font-weight: 600; }
QLabel#Warning { color: #946200; font-weight: 600; }
QLabel#Danger { color: #B42318; font-weight: 600; }
QLabel#BuildLabel { color: #98A4B3; font-size: 9px; }
QLabel#StatusBarText { color: #68788E; font-size: 10px; font-weight: 600; letter-spacing: 0.4px; }
QLabel#InfoStrip {
    background: #F8FAFD;
    color: #667085;
    border: 1px solid #E4E9F0;
    border-radius: 7px;
    padding: 8px 10px;
}
QPushButton {
    background: #FFFFFF;
    border: 1px solid #C8D2DF;
    border-radius: 6px;
    padding: 7px 12px;
}
QPushButton:hover { border-color: #2B6DEB; background: #FBFDFF; }
QPushButton:pressed { background: #F1F5F9; }
QPushButton#PrimaryButton {
    background: #2B6DEB;
    color: white;
    border: 1px solid #2B6DEB;
    font-weight: 600;
}
QPushButton#PrimaryButton:hover { background: #225CC8; }
QPushButton#NavStepButton {
    text-align: left;
    padding: 0;
    border: 0;
    border-radius: 6px;
    background: transparent;
}
QPushButton#NavStepButton:hover { background: #F3F6FA; }
QPushButton#NavStepButton:checked { background: transparent; }
QLabel#NavNumber {
    background: #FFFFFF;
    color: #637287;
    border: 1px solid #D7DFE8;
    border-radius: 11px;
    font-weight: 700;
    font-size: 10px;
}
QPushButton#NavStepButton:checked QLabel#NavNumber {
    background: #2B6DEB;
    color: #FFFFFF;
    border-color: #2B6DEB;
}
QWidget#NavTextColumn { background: transparent; }
QLabel#NavTitle { color: #344054; font-weight: 600; }
QPushButton#NavStepButton:checked QLabel#NavTitle { color: #174EA6; font-weight: 700; }
QLabel#NavStatusText { color: #98A2B3; font-size: 9px; }
QLabel#NavStatusText[statusKind="active"], QLabel#NavStatusText[statusKind="running"] { color: #2B6DEB; }
QLabel#NavStatusText[statusKind="complete"] { color: #0F7A50; }
QLabel#NavStatusText[statusKind="warning"] { color: #946200; }
QLineEdit, QComboBox, QSpinBox {
    background: #FFFFFF;
    border: 1px solid #C8D2DF;
    border-radius: 6px;
    padding: 7px 9px;
    min-height: 22px;
    selection-background-color: #DCE8FF;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: #2B6DEB; }
QLineEdit:disabled { background: #F3F6FA; color: #6F7E91; }
QCheckBox, QRadioButton { spacing: 7px; background: transparent; }
QGroupBox {
    background: #FFFFFF;
    border: 1px solid #DDE4ED;
    border-radius: 9px;
    margin-top: 10px;
    padding-top: 8px;
    font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 11px; padding: 0 5px; color: #344054; }
QProgressBar {
    background: #E5EBF3;
    border: 0;
    border-radius: 4px;
    height: 10px;
    text-align: center;
}
QProgressBar::chunk { background: #2B6DEB; border-radius: 4px; }
QTableWidget {
    background: #FFFFFF;
    alternate-background-color: #F8FAFD;
    border: 1px solid #DDE4ED;
    gridline-color: #E4E9F0;
}
QHeaderView::section {
    background: #F3F6FA;
    border: 0;
    border-bottom: 1px solid #DDE4ED;
    padding: 7px;
    font-weight: 600;
    color: #334155;
}
QScrollArea { background: transparent; border: 0; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 3px 1px; }
QScrollBar::handle:vertical { background: #C6D0DC; min-height: 36px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

# v0.5 research-console extensions
APP_STYLE += """
QFrame#ResearchStrip {
    background: #0F2742;
    border: 1px solid #163B62;
    border-radius: 9px;
}
QFrame#ResearchStrip QFrame#MetricCell {
    border-right: 1px solid #29455F;
}
QFrame#ResearchStrip QLabel#MetricKicker { color: #91A9C3; }
QFrame#ResearchStrip QLabel#MetricValue { color: #F7FAFC; }
QFrame#ResearchStrip QLabel#MonoValue { color: #DDEBFF; }
QFrame#ResearchStrip QLabel#MetricDetail { color: #9EB0C2; }
QFrame#DataPanel {
    background: #FFFFFF;
    border: 1px solid #D8E1EB;
    border-radius: 9px;
}
QLabel#DataPanelTitle {
    color: #102A43;
    font-size: 13px;
    font-weight: 700;
}
QLabel#DataPanelSubtitle {
    color: #728197;
    font-size: 10px;
}
QLabel#MonoValue {
    color: #1A365D;
    font-family: 'Cascadia Mono', Consolas, monospace;
    font-size: 13px;
    font-weight: 700;
}
QLabel#StatusPill {
    border-radius: 10px;
    padding: 3px 8px;
    min-width: 58px;
    font-size: 9px;
    font-weight: 700;
}
QLabel#StatusPill[statusKind="complete"] {
    color: #096B48;
    background: #E9F8F1;
    border: 1px solid #CBEBDD;
}
QLabel#StatusPill[statusKind="warning"] {
    color: #8A5A00;
    background: #FFF6E0;
    border: 1px solid #F2D99A;
}
QLabel#StatusPill[statusKind="info"] {
    color: #245EA8;
    background: #EDF5FF;
    border: 1px solid #D4E5FB;
}
QLabel#StatusPill[statusKind="pending"] {
    color: #667085;
    background: #F4F6F8;
    border: 1px solid #E1E6EC;
}
QFrame#PipelineNode {
    background: #F8FAFD;
    border: 1px solid #DFE6EE;
    border-radius: 8px;
}
QLabel#PipelineStage {
    color: #2B6DEB;
    font-family: 'Cascadia Mono', Consolas, monospace;
    font-size: 10px;
    font-weight: 700;
}
QLabel#PipelineTitle { color: #102A43; font-size: 12px; font-weight: 700; }
QLabel#PipelineDetail { color: #728197; font-size: 10px; }
QFrame#MethodRow {
    background: transparent;
    border: 0;
    border-bottom: 1px solid #E7ECF2;
}
QLabel#MethodKey { color: #637287; font-size: 10px; font-weight: 600; }
QLabel#MethodValue { color: #142033; font-size: 11px; font-weight: 600; }
QLabel#PercentValue { color: #0F2742; font-size: 24px; font-weight: 700; }
QLabel#LargeStatus { color: #8A5A00; font-size: 22px; font-weight: 700; }
QLabel#QaValue { color: #102A43; font-size: 15px; font-weight: 700; }
QLabel#TinyLabel { color: #8A98AA; font-size: 9px; font-weight: 700; letter-spacing: 0.6px; }
QListWidget#ActivityList {
    background: #FAFCFF;
    border: 1px solid #E1E7EF;
    border-radius: 6px;
    padding: 4px;
}
QListWidget#WeatherLibraryResults {
    background: #FAFCFF;
    border: 1px solid #DDE4ED;
    border-radius: 7px;
    padding: 3px;
}
QListWidget#WeatherLibraryResults::item {
    padding: 7px 8px;
    border-radius: 5px;
}
QListWidget#WeatherLibraryResults::item:selected {
    background: #E8F0FF;
    color: #174EA6;
}
QTextEdit#LogConsole {
    background: #0D1B2A;
    color: #CFE2F3;
    border: 1px solid #21374C;
    border-radius: 6px;
    font-family: 'Cascadia Mono', Consolas, monospace;
    font-size: 10px;
}
"""


def scaled_app_style(scale_name: str = "standard") -> str:
    """Return the existing theme with only declared font-size px values scaled."""
    if scale_name == "standard":
        return APP_STYLE
    from .i18n import text_scale_factor
    import re

    factor = text_scale_factor(scale_name)

    def repl(match):
        size = int(match.group(1))
        scaled = max(7, int(size * factor + 0.5))
        return f"font-size: {scaled}px"

    return re.sub(r"font-size:\s*(\d+)px", repl, APP_STYLE)
