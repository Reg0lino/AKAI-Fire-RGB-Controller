# AKAI_Fire_RGB_Controller/gui/ambient_mode_settings_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal

# --- Slider Constants (Copied from capture_preview_dialog.py for consistency) ---
SLIDER_MIN_FACTOR_VAL = 0
SLIDER_MAX_FACTOR_VAL = 400
SLIDER_MIN_HUE = -180
SLIDER_MAX_HUE = 180

# --- Default Values (Copied from capture_preview_dialog.py for consistency) ---
DEFAULT_BRIGHTNESS_FACTOR = 1.0
DEFAULT_SATURATION_FACTOR = 1.75
DEFAULT_CONTRAST_FACTOR = 1.0
DEFAULT_HUE_SHIFT = 0

class AmbientModeSettingsDialog(QDialog):
    """A simplified dialog for adjusting colors in non-grid ambient modes."""
    sampling_parameters_changed = pyqtSignal(dict)
    cycle_monitor_requested = pyqtSignal()
    dialog_closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎨 Ambient Mode Color Adjustments")
        self.setFixedSize(400, 220)  # A compact, fixed size is perfect here
        # --- UI Element Declarations ---
        self.brightness_slider: QSlider | None = None
        self.brightness_value_label: QLabel | None = None
        self.brightness_reset_button: QPushButton | None = None
        self.saturation_slider: QSlider | None = None
        self.saturation_value_label: QLabel | None = None
        self.saturation_reset_button: QPushButton | None = None
        self.contrast_slider: QSlider | None = None
        self.contrast_value_label: QLabel | None = None
        self.contrast_reset_button: QPushButton | None = None
        self.hue_slider: QSlider | None = None
        self.hue_value_label: QLabel | None = None
        self.hue_reset_button: QPushButton | None = None
        self.cycle_monitor_button: QPushButton | None = None
        self.current_params = {}  # This will be populated by the manager
        self._init_ui()
        self._connect_signals()
        self._update_all_slider_value_labels()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # Helper function to create a slider row
        def create_slider_row(label_text, min_val, max_val, initial_val):
            layout = QHBoxLayout()
            label = QLabel(label_text)
            label.setMinimumWidth(70)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(min_val, max_val)
            slider.setValue(initial_val)
            value_label = QLabel()
            value_label.setMinimumWidth(55)
            reset_button = QPushButton("⟳")
            reset_button.setFixedSize(24, 24)
            reset_button.setObjectName("ResetButton")
            layout.addWidget(label)
            layout.addWidget(slider)
            layout.addWidget(value_label)
            layout.addWidget(reset_button)
            return layout, slider, value_label, reset_button
        # Color Adjustments Group
        adjustments_group = QGroupBox("Color Adjustments")
        adjustments_layout = QVBoxLayout(adjustments_group)
        bri_row_layout, self.brightness_slider, self.brightness_value_label, self.brightness_reset_button = create_slider_row(
            "Brightness:", SLIDER_MIN_FACTOR_VAL, SLIDER_MAX_FACTOR_VAL, self._factor_to_slider(DEFAULT_BRIGHTNESS_FACTOR))
        adjustments_layout.addLayout(bri_row_layout)
        sat_row_layout, self.saturation_slider, self.saturation_value_label, self.saturation_reset_button = create_slider_row(
            "Saturation:", SLIDER_MIN_FACTOR_VAL, SLIDER_MAX_FACTOR_VAL, self._factor_to_slider(DEFAULT_SATURATION_FACTOR))
        adjustments_layout.addLayout(sat_row_layout)
        con_row_layout, self.contrast_slider, self.contrast_value_label, self.contrast_reset_button = create_slider_row(
            "Contrast:", SLIDER_MIN_FACTOR_VAL, SLIDER_MAX_FACTOR_VAL, self._factor_to_slider(DEFAULT_CONTRAST_FACTOR))
        adjustments_layout.addLayout(con_row_layout)
        hue_row_layout, self.hue_slider, self.hue_value_label, self.hue_reset_button = create_slider_row(
            "Hue Shift:", SLIDER_MIN_HUE, SLIDER_MAX_HUE, int(round(DEFAULT_HUE_SHIFT)))
        adjustments_layout.addLayout(hue_row_layout)
        main_layout.addWidget(adjustments_group)
        self.cycle_monitor_button = QPushButton("🔄 Cycle Monitor")
        self.cycle_monitor_button.setFixedWidth(150)
        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self.cycle_monitor_button)
        button_layout.addStretch(1)
        main_layout.addLayout(button_layout)
        main_layout.addStretch(1)

    def _connect_signals(self):
        self.saturation_slider.valueChanged.connect(
            self._on_adjustment_slider_changed)
        self.contrast_slider.valueChanged.connect(
            self._on_adjustment_slider_changed)
        self.brightness_slider.valueChanged.connect(
            self._on_adjustment_slider_changed)
        self.hue_slider.valueChanged.connect(
            self._on_adjustment_slider_changed)
        self.brightness_reset_button.clicked.connect(lambda: self.brightness_slider.setValue(
            self._factor_to_slider(DEFAULT_BRIGHTNESS_FACTOR)))
        self.saturation_reset_button.clicked.connect(lambda: self.saturation_slider.setValue(
            self._factor_to_slider(DEFAULT_SATURATION_FACTOR)))
        self.contrast_reset_button.clicked.connect(lambda: self.contrast_slider.setValue(
            self._factor_to_slider(DEFAULT_CONTRAST_FACTOR)))
        self.hue_reset_button.clicked.connect(
            lambda: self.hue_slider.setValue(DEFAULT_HUE_SHIFT))
        self.cycle_monitor_button.clicked.connect(self.cycle_monitor_requested)

    def _slider_to_factor(self, slider_int_val: int) -> float:
        return float(slider_int_val) / 100.0

    def _factor_to_slider(self, factor_float_val: float) -> int:
        return int(round(factor_float_val * 100.0))

    def _update_all_slider_value_labels(self):
        adj = self.current_params.get('adjustments', {})
        self.brightness_value_label.setText(
            f"{adj.get('brightness', DEFAULT_BRIGHTNESS_FACTOR):.2f}x")
        self.saturation_value_label.setText(
            f"{adj.get('saturation', DEFAULT_SATURATION_FACTOR):.2f}x")
        self.contrast_value_label.setText(
            f"{adj.get('contrast', DEFAULT_CONTRAST_FACTOR):.2f}x")
        self.hue_value_label.setText(
            f"{int(round(adj.get('hue_shift', DEFAULT_HUE_SHIFT))):+d}°")

    def _on_adjustment_slider_changed(self):
        if 'adjustments' not in self.current_params:
            self.current_params['adjustments'] = {}
        self.current_params['adjustments']['saturation'] = self._slider_to_factor(
            self.saturation_slider.value())
        self.current_params['adjustments']['contrast'] = self._slider_to_factor(
            self.contrast_slider.value())
        self.current_params['adjustments']['brightness'] = self._slider_to_factor(
            self.brightness_slider.value())
        self.current_params['adjustments']['hue_shift'] = float(
            self.hue_slider.value())
        self._update_all_slider_value_labels()
        self._emit_sampling_parameters_changed()

    def _emit_sampling_parameters_changed(self):
        self.sampling_parameters_changed.emit(self.current_params)

    def set_current_parameters_from_main(self, params: dict):
        self.current_params = params
        adjustments = self.current_params.get('adjustments', {})
        all_sliders = [self.brightness_slider, self.saturation_slider,
                        self.contrast_slider, self.hue_slider]
        for s in all_sliders:
            s.blockSignals(True)
        self.brightness_slider.setValue(self._factor_to_slider(
            adjustments.get('brightness', DEFAULT_BRIGHTNESS_FACTOR)))
        self.saturation_slider.setValue(self._factor_to_slider(
            adjustments.get('saturation', DEFAULT_SATURATION_FACTOR)))
        self.contrast_slider.setValue(self._factor_to_slider(
            adjustments.get('contrast', DEFAULT_CONTRAST_FACTOR)))
        self.hue_slider.setValue(
            int(round(adjustments.get('hue_shift', DEFAULT_HUE_SHIFT))))
        for s in all_sliders:
            s.blockSignals(False)
        self._update_all_slider_value_labels()

    def update_sliders_from_external_adjustments(self, new_adjustments: dict):
        self.set_current_parameters_from_main({'adjustments': new_adjustments})

    def closeEvent(self, event):
        self.dialog_closed.emit()
        super().closeEvent(event)

    def reject(self):
        self.dialog_closed.emit()
        super().reject()
