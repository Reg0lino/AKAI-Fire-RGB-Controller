# AKAI_Fire_RGB_Controller/gui/main_window.py
from .visualizer_settings_dialog import VisualizerSettingsDialog
from .audio_visualizer_ui_manager import AudioVisualizerUIManager
from appdirs import user_config_dir
import sys
import json
import os
import re
import time

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QComboBox, QSizePolicy, QSpacerItem,
    QStatusBar, QMenu, QMessageBox, QDial, QFrame, QDialog
)
USER_PRESETS_APP_FOLDER_NAME = "Akai Fire RGB Controller User Presets"
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal, QPoint, QEvent, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QPalette, QAction, QMouseEvent, QKeySequence, QIcon, QPixmap,
    QImage, QPainter, QCloseEvent, QKeyEvent, QPen, QBrush, QPolygon
)

class StaticKnobWidget(QWidget):
    """A custom widget to statically draw the visual appearance of a knob."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0.0  # Angle for the indicator. 0 is up, -135 is bottom-left, 135 is bottom-right.
        self.knob_body_color = QColor("#1A1A1A")
        self.knob_border_color = QColor("#2A2A2A")
        self.indicator_body_color = QColor("#505050")
        self.indicator_border_color = QColor("#666666")
        self.tick_color = QColor("#444444")

    def set_indicator_angle(self, angle: float):
        """Sets the angle of the indicator. Angle should be between -135 and 135."""
        clamped_angle = max(-135.0, min(angle, 135.0))
        if abs(self._angle - clamped_angle) > 0.1:
            self._angle = clamped_angle
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = min(self.width(), self.height())
        painter.translate(self.width() / 2.0, self.height() / 2.0)
        
        knob_rect = QRectF(-side/2 + 2, -side/2 + 2, side - 4, side - 4)
        painter.setBrush(QBrush(self.knob_body_color))
        painter.setPen(QPen(self.knob_border_color, 1.5))
        painter.drawEllipse(knob_rect)
        painter.setPen(QPen(self.tick_color, 1.5))
        tick_outer_radius = (side / 2.0) - 2.5
        tick_inner_radius = tick_outer_radius - 4
        # Draw static ticks around the circumference
        for angle in range(0, 360, 15):
            if 45 < angle < 135: # Create a gap at the bottom
                continue
            painter.save()
            painter.rotate(angle)
            painter.drawLine(int(tick_inner_radius), 0, int(tick_outer_radius), 0)
            painter.restore()
        # Draw the indicator handle, rotating from the top (0 degrees)
        painter.save()
        painter.rotate(self._angle)
        
        indicator_radius = (side / 2.0) * 0.60
        indicator_size = side * 0.18
        
        indicator_rect = QRectF(
            -indicator_size / 2, 
            -indicator_radius - (indicator_size / 2),
            indicator_size, 
            indicator_size
        )
        
        painter.setBrush(QBrush(self.indicator_body_color))
        painter.setPen(QPen(self.indicator_border_color, 1))
        painter.drawEllipse(indicator_rect)
        painter.restore()

# --- Project-specific Imports ---
try:
    from ..utils import get_resource_path
except ImportError:
    from utils import get_resource_path
    print("MainWindow INFO: Used fallback import for utils.get_resource_path.")

try:
    from oled_utils import oled_renderer
    MAIN_WINDOW_OLED_RENDERER_AVAILABLE = True
except ImportError:
    print("MainWindow WARNING: oled_renderer module not found. OLED mirror/startup may be affected.")
    MAIN_WINDOW_OLED_RENDERER_AVAILABLE = False

try:
    from doom_feature.doom_game_controller import (
        DoomGameController, RaycasterEngine, PLAYER_MAX_HP,
        PAD_DOOM_FORWARD, PAD_DOOM_BACKWARD,
        PAD_DOOM_STRAFE_LEFT, PAD_DOOM_STRAFE_RIGHT,
        PAD_DOOM_TURN_LEFT_MAIN, PAD_DOOM_TURN_RIGHT_MAIN,
        PAD_DOOM_TURN_LEFT_ALT, PAD_DOOM_TURN_RIGHT_ALT,
        PAD_DOOM_RUN, PAD_DOOM_SHOOT
    )
    print("MW INFO: Successfully imported DoomGameController, RaycasterEngine, and DOOM Pad Constants.")
    DOOM_MODULE_LOADED = True
except ImportError as e:
    print(
        f"MW WARNING: Could not import from doom_feature.doom_game_controller: {e}. DOOM feature will be non-functional.")

try:
    from doom_feature.doom_game_controller import DoomGameController, RaycasterEngine, PLAYER_MAX_HP
    print("MW INFO: Successfully imported DoomGameController and RaycasterEngine from doom_feature.doom_game_controller.")
    DOOM_MODULE_LOADED = True
except ImportError as e:
    print(
        f"MW WARNING: Could not import from doom_feature.doom_game_controller: {e}. DOOM feature will be non-functional.")
    DOOM_MODULE_LOADED = False

from .oled_customizer_dialog import OLEDCustomizerDialog
from .app_guide_dialog import AppGuideDialog
from .doom_instructions_dialog import DoomInstructionsDialog
class oled_renderer_placeholder_mw:
        OLED_WIDTH = 128
        OLED_HEIGHT = 64
        @staticmethod
        def generate_fire_startup_animation(width=128, height=64): return []
        @staticmethod
        def _unpack_fire_7bit_stream_to_logical_image(
            packed_stream, width, height): return None

if 'oled_renderer' not in globals() or globals().get('oled_renderer') is None:
    oled_renderer = oled_renderer_placeholder_mw()

from .color_picker_manager import ColorPickerManager
from .static_layouts_manager import StaticLayoutsManager
from .interactive_pad_grid import InteractivePadGridFrame
from .screen_sampler_manager import ScreenSamplerManager
from .animator_manager_widget import AnimatorManagerWidget
from .audio_visualizer_ui_manager import AudioVisualizerUIManager
from managers.audio_visualizer_manager import AudioVisualizerManager
from hardware.akai_fire_controller import AkaiFireController
from managers.oled_display_manager import OLEDDisplayManager
from managers.hardware_input_manager import HardwareInputManager

try:
    from ..animator.controls_widget import ICON_COPY, ICON_CUT, ICON_DUPLICATE, ICON_DELETE, ICON_ADD_BLANK
except ImportError:
    from animator.controls_widget import ICON_COPY, ICON_CUT, ICON_DUPLICATE, ICON_DELETE, ICON_ADD_BLANK
    print("MainWindow INFO: Used fallback import for animator.controls_widget icons.")
try:
    from features.screen_sampler_core import ScreenSamplerCore
except ImportError:
    print("MainWindow WARNING: Could not import ScreenSamplerCore for default adjustments.")

    class ScreenSamplerCore:
        DEFAULT_ADJUSTMENTS = {'brightness': 1.0, 'contrast': 1.0,
                            'saturation': 1.0, 'hue_shift': 0.0}  # ensure float for hue

MW_FPS_MIN_DISCRETE_VALUES = [0.5, 1.0, 2.0, 3.0, 4.0, 5.0]
MW_FPS_LINEAR_START_VALUE = 6.0
MW_FPS_MAX_TARGET_VALUE = 90.0  # Or your chosen max for Knob 4
_MW_NUM_DISCRETE_FPS_STEPS = len(MW_FPS_MIN_DISCRETE_VALUES)
_MW_SLIDER_IDX_FOR_LINEAR_START = _MW_NUM_DISCRETE_FPS_STEPS
MW_ANIMATOR_FPS_KNOB_MIN_SLIDER_VAL = 0  # Raw min for QDial range
MW_ANIMATOR_FPS_KNOB_MAX_SLIDER_VAL = _MW_SLIDER_IDX_FOR_LINEAR_START + \
    int(MW_FPS_MAX_TARGET_VALUE - MW_FPS_LINEAR_START_VALUE)
# This should result in 0 to 90 for the example values

# Knob step for physical encoder (delta is +/-1, maps to 1 step on the raw slider value)
MW_ANIMATOR_SPEED_KNOB_STEP = 1

# --- Constants ---
INITIAL_WINDOW_WIDTH = 1100
INITIAL_WINDOW_HEIGHT = 900
PRESETS_BASE_DIR_NAME = "presets"
APP_NAME = "AKAI_Fire_RGB_Controller"
APP_AUTHOR = "Reg0lino"
USER_PRESETS_APP_FOLDER_NAME = "Akai Fire RGB Controller User Presets"
OLED_MIRROR_WIDTH = 128
OLED_MIRROR_HEIGHT = 64
OLED_MIRROR_SCALE = 1.2
OLED_CONFIG_FILENAME = "oled_config.json"
DEFAULT_OLED_ACTIVE_GRAPHIC_FALLBACK_PATH: str | None = None
DEFAULT_OLED_SCROLL_DELAY_MS_FALLBACK: int = 180
DEFAULT_OLED_FONT_FAMILY_FALLBACK: str = "Arial"
DEFAULT_OLED_FONT_SIZE_PX_FALLBACK: int = 20
USER_OLED_PRESETS_DIR_NAME = "OLEDCustomPresets"
USER_OLED_TEXT_ITEMS_SUBDIR = "TextItems"
USER_OLED_ANIM_ITEMS_SUBDIR = "ImageAnimations"

# --- Path Helper Functions (Module Level - Keep as they are) ---
from .visualizer_settings_dialog import VisualizerSettingsDialog  # Add this import at the top, adjust path as needed

def get_user_documents_presets_path(app_specific_folder_name: str = USER_PRESETS_APP_FOLDER_NAME) -> str:
    try:
        if sys.platform == "win32":
            import ctypes.wintypes
            CSIDL_PERSONAL = 5
            SHGFP_TYPE_CURRENT = 0
            import ctypes
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(
                None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf)
            documents_path = buf.value or os.path.join(
                os.path.expanduser("~"), "Documents")
        elif sys.platform == "darwin":
            documents_path = os.path.join(os.path.expanduser("~"), "Documents")
        else:
            documents_path = os.environ.get(
                'XDG_DOCUMENTS_DIR', os.path.join(os.path.expanduser("~"), "Documents"))
            if not os.path.isdir(documents_path):
                documents_path = os.path.join(
                    os.path.expanduser("~"), "Documents")
        if not os.path.isdir(documents_path):
            documents_path = os.path.expanduser("~")
        app_presets_dir = os.path.join(
            documents_path, app_specific_folder_name)
        os.makedirs(app_presets_dir, exist_ok=True)
        return app_presets_dir
    except Exception as e:
        print(f"WARNING: User presets path error (CWD fallback): {e}")
        fallback_dir = os.path.join(
            os.getcwd(), "user_presets_fallback_mw_hr1")
        os.makedirs(fallback_dir, exist_ok=True)
        return fallback_dir

def get_user_config_file_path(filename: str) -> str:
    config_dir_to_use = ""
    try:
        is_packaged = getattr(
            sys, 'frozen', False) and hasattr(sys, '_MEIPASS')
        if is_packaged:
            config_dir_to_use = user_config_dir(
                APP_NAME, APP_AUTHOR, roaming=True)
        else:
            try:
                current_file_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.dirname(current_file_dir)
            except NameError:
                project_root = os.getcwd()
            config_dir_to_use = os.path.join(project_root, "user_settings")
        os.makedirs(config_dir_to_use, exist_ok=True)
        return os.path.join(config_dir_to_use, filename)
    except Exception as e:
        print(
            f"WARNING: Config path error for '{filename}' (CWD fallback): {e}")
        fallback_dir = os.path.join(
            os.getcwd(), "user_settings_fallback_mw_hr1")
        os.makedirs(fallback_dir, exist_ok=True)
        return os.path.join(fallback_dir, filename)

class MainWindow(QMainWindow):
    OLED_NAVIGATION_FOCUS_OPTIONS = ["animator", "static_layouts"]
    SAMPLER_BRIGHTNESS_KNOB_MIN, SAMPLER_BRIGHTNESS_KNOB_MAX = 0, 400
    SAMPLER_SATURATION_KNOB_MIN, SAMPLER_SATURATION_KNOB_MAX = 0, 400
    SAMPLER_CONTRAST_KNOB_MIN, SAMPLER_CONTRAST_KNOB_MAX = 0, 400
    SAMPLER_HUE_KNOB_MIN, SAMPLER_HUE_KNOB_MAX = -180, 180
    SAMPLER_FACTOR_KNOB_STEP = 4
    SAMPLER_HUE_KNOB_STEP = 2
    GLOBAL_BRIGHTNESS_KNOB_STEP = 1
    ANIMATOR_SPEED_KNOB_STEP = 1

# --- GROUP 1: CORE HELPER METHODS CALLED EARLY BY __init__ ---
    def _get_presets_base_dir_path(self) -> str:
        return get_resource_path(PRESETS_BASE_DIR_NAME)

    def _set_window_icon(self):
        try:
            icon_path = get_resource_path(os.path.join(
                "resources", "icons", "app_icon.png"))
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
            # else: print(f"MW WARNING: Window icon not found at '{icon_path}'") # Optional
        except Exception as e:
            print(f"MW ERROR: Could not set window icon: {e}")

    def _get_oled_config_filepath(self) -> str:
        return get_user_config_file_path(OLED_CONFIG_FILENAME)

    def _load_oled_config(self):
        filepath = self._get_oled_config_filepath()
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.active_graphic_item_relative_path = config.get("active_graphic_item_path",
                                                                    config.get("default_startup_item_path",
                                                                                DEFAULT_OLED_ACTIVE_GRAPHIC_FALLBACK_PATH))
                self.oled_global_scroll_delay_ms = config.get(
                    "global_scroll_delay_ms", DEFAULT_OLED_SCROLL_DELAY_MS_FALLBACK)
                self.current_cued_text_item_path = config.get(
                    "cued_text_item_path", None)
                self.current_cued_anim_item_path = config.get(
                    "cued_anim_item_path", None)
            else:
                self.active_graphic_item_relative_path = DEFAULT_OLED_ACTIVE_GRAPHIC_FALLBACK_PATH
                self.oled_global_scroll_delay_ms = DEFAULT_OLED_SCROLL_DELAY_MS_FALLBACK
                self.current_cued_text_item_path = None
                self.current_cued_anim_item_path = None
                self._save_oled_config()
        except json.JSONDecodeError as e:
            print(
                f"MW WARNING: Error decoding OLED config: {e}. Using defaults.")
            self.active_graphic_item_relative_path = DEFAULT_OLED_ACTIVE_GRAPHIC_FALLBACK_PATH
            self.oled_global_scroll_delay_ms = DEFAULT_OLED_SCROLL_DELAY_MS_FALLBACK
            self.current_cued_text_item_path = None
            self.current_cued_anim_item_path = None
            self._save_oled_config()
        except Exception as e:
            print(
                f"MW WARNING: Generic error loading OLED config: {e}. Using defaults.")
            self.active_graphic_item_relative_path = DEFAULT_OLED_ACTIVE_GRAPHIC_FALLBACK_PATH
            self.oled_global_scroll_delay_ms = DEFAULT_OLED_SCROLL_DELAY_MS_FALLBACK
            self.current_cued_text_item_path = None
            self.current_cued_anim_item_path = None

    def _save_oled_config(self):
        # ... (definition as provided previously, using self.active_graphic_item_relative_path) ...
        filepath = self._get_oled_config_filepath()
        config = {
            "active_graphic_item_path": self.active_graphic_item_relative_path,
            "global_scroll_delay_ms": self.oled_global_scroll_delay_ms,
            "cued_text_item_path": self.current_cued_text_item_path,
            "cued_anim_item_path": self.current_cued_anim_item_path
        }
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"MW ERROR: Could not save OLED config: {e}")

    def _scan_available_app_fonts(self) -> list[str]:
        app_fonts_list = []
        try:
            fonts_dir = get_resource_path(os.path.join("resources", "fonts"))
            if os.path.isdir(fonts_dir):
                for filename in os.listdir(fonts_dir):
                    if filename.lower().endswith((".ttf", ".otf")):
                        app_fonts_list.append(filename)
            app_fonts_list.sort()
        except Exception as e:
            print(f"MW Error scanning app fonts: {e}")
        return app_fonts_list

    def _get_user_oled_presets_path(self, subfolder: str | None = None) -> str:
        base = self.user_oled_presets_base_path
        target_path = os.path.join(base, subfolder) if subfolder else base
        try:
            os.makedirs(target_path, exist_ok=True)
        except OSError as e:
            print(
                f"MainWindow Error: Could not create OLED presets directory '{target_path}': {e}")
            dev_fallback_base = os.path.join(
                os.getcwd(), "user_dev_oled_presets")
            target_path = os.path.join(
                dev_fallback_base, subfolder) if subfolder else dev_fallback_base
            # Ensure specific subfolder in fallback exists
            os.makedirs(target_path, exist_ok=True)
            print(
                f"MainWindow Warning: Using fallback OLED presets directory for this operation: '{target_path}'")
        return target_path

    def _scan_available_oled_items(self) -> list[dict]:
        if not hasattr(self, 'available_oled_items_cache'):
            self.available_oled_items_cache = []
        self.available_oled_items_cache.clear()
        text_items_dir_path = self._get_user_oled_presets_path(
            USER_OLED_TEXT_ITEMS_SUBDIR)
        anim_items_dir_path = self._get_user_oled_presets_path(
            USER_OLED_ANIM_ITEMS_SUBDIR)
        item_sources_config = [
            {"dir_path": text_items_dir_path, "type_label": "text",
                "relative_subdir": USER_OLED_TEXT_ITEMS_SUBDIR},
            {"dir_path": anim_items_dir_path, "type_label": "animation",
                "relative_subdir": USER_OLED_ANIM_ITEMS_SUBDIR},
        ]
        for source_info in item_sources_config:
            dir_path = source_info["dir_path"]
            item_type = source_info["type_label"]
            relative_subdir = source_info["relative_subdir"]
            if os.path.isdir(dir_path):
                for filename in os.listdir(dir_path):
                    if filename.lower().endswith(".json"):
                        full_path = os.path.join(dir_path, filename)
                        try:
                            with open(full_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            item_name = data.get(
                                "item_name", os.path.splitext(filename)[0])
                            
                            # Create the relative path (filename within its type subfolder)
                            relative_item_path = os.path.join(
                                relative_subdir, filename)
                            # Ensure consistent path separators (forward slashes)
                            relative_item_path = relative_item_path.replace(os.path.sep, '/')
                                
                            self.available_oled_items_cache.append({
                                'name': item_name,
                                'relative_path': relative_item_path, # <<< CORRECTED KEY
                                'type': item_type,
                                'full_path': full_path  # Keep full path for loading
                            })
                        except Exception as e:
                            print(
                                f"MW Error processing OLED item '{full_path}': {e}")
        self.available_oled_items_cache.sort(key=lambda x: x['name'].lower())
        return self.available_oled_items_cache

    def _load_oled_item_data(self, relative_item_path: str | None) -> dict | None:
        if not relative_item_path:
            return None
        if not hasattr(self, 'user_oled_presets_base_path'):
            print(
                "MW CRITICAL: user_oled_presets_base_path not set before _load_oled_item_data.")
            return None
        full_item_path = os.path.join(
            self.user_oled_presets_base_path, relative_item_path)
        if os.path.exists(full_item_path):
            try:
                with open(full_item_path, 'r', encoding='utf-8') as f:
                    item_data = json.load(f)
                return item_data
            except Exception as e:
                print(
                    f"MW Error loading OLED item from '{full_item_path}': {e}")
                return None
        return None

    def _load_and_apply_active_graphic(self):
        if not self.oled_display_manager:
            print("MW CRITICAL: ODM None in _load_and_apply_active_graphic.")
            return
        active_graphic_data = self._load_oled_item_data(
            self.active_graphic_item_relative_path)
        if active_graphic_data:
            self.oled_display_manager.set_active_graphic(active_graphic_data)
        else:
            self.oled_display_manager.set_active_graphic(None)

    def _on_builtin_oled_startup_animation_finished(self):
        pass

    def ensure_user_dirs_exist(self):
        user_static_layouts_base = os.path.join(
            self.user_documents_presets_path, "static")
        user_sequences_base = os.path.join(
            self.user_documents_presets_path, "sequences")
        paths_to_create = [
            os.path.join(user_static_layouts_base, "user"),
            os.path.join(user_sequences_base, "user"),
            os.path.join(user_sequences_base, "sampler_recordings")
        ]
        for path in paths_to_create:
            try:
                os.makedirs(path, exist_ok=True)
            except Exception as e:
                print(
                    f"MW WARNING: Could not create user directory '{path}': {e}")

# --- GROUP 2: UI BUILDING HELPER METHODS ---
    def _init_ui_layout(self):
        """
        Initializes the main window layout structure:
        - Central widget
        - Main horizontal layout for left and right panels
        - Left vertical panel layout
        - Right vertical panel layout
        - Status bar
        """
        # print("MW DEBUG: _init_ui_layout START") # For tracing
        # 1. Create the central widget and set it on the QMainWindow
        self.central_widget_main = QWidget()
        self.setCentralWidget(self.central_widget_main)
        # print(f"MW DEBUG: _init_ui_layout - Central widget created: {self.central_widget_main}")
        # 2. Create the main application layout (QHBoxLayout) for the central widget
        # This will hold the left and right panels.
        self.main_app_layout = QHBoxLayout(self.central_widget_main) # Set layout directly on central_widget_main
        self.main_app_layout.setSpacing(10)
        self.main_app_layout.setContentsMargins(5, 5, 5, 5) # Small margins around the entire app content
        # print(f"MW DEBUG: _init_ui_layout - Main app layout (QHBoxLayout) created: {self.main_app_layout}")
        # 3. --- Left Panel Setup ---
        # Create a QWidget to act as the container for the left panel's content
        self.left_panel_widget = QWidget()
        self.left_panel_widget.setObjectName("LeftPanelWidget") # For styling if needed
        # Create a QVBoxLayout for the left panel's content
        self.left_panel_layout = QVBoxLayout(self.left_panel_widget) # Set layout on the left_panel_widget
        self.left_panel_layout.setContentsMargins(0, 0, 0, 0) # No margins within the left panel itself
        self.left_panel_layout.setSpacing(8) # Spacing between items in the left panel
        # Add the left_panel_widget (which now has its QVBoxLayout) to the main_app_layout
        self.main_app_layout.addWidget(self.left_panel_widget, 2)  # Stretch factor 2 (takes 2/3 of available width)
        # print(f"MW DEBUG: _init_ui_layout - Left panel widget and layout created, added to main layout. Layout: {self.left_panel_layout}")
        # 4. --- Right Panel Setup ---
        # Create a QWidget for the right panel
        self.right_panel_widget = QWidget()
        self.right_panel_widget.setObjectName("RightPanelWidget")
        # Create a QVBoxLayout for the right panel's content
        self.right_panel_layout_v = QVBoxLayout(self.right_panel_widget) # Set layout on the right_panel_widget
        # self.right_panel_layout_v.setContentsMargins(0,0,0,0) # Optional: if you want margins inside right panel
        # self.right_panel_layout_v.setSpacing(8)               # Optional: spacing for items in right panel
        # Set size constraints for the right panel
        self.right_panel_widget.setMinimumWidth(380) 
        self.right_panel_widget.setMaximumWidth(420) 
        self.right_panel_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding) # Fixed width, expanding height
        # Add the right_panel_widget to the main_app_layout
        self.main_app_layout.addWidget(self.right_panel_widget, 1)  # Stretch factor 1 (takes 1/3 of available width)
        # print(f"MW DEBUG: _init_ui_layout - Right panel widget and layout created, added to main layout. Layout: {self.right_panel_layout_v}")
        # 5. --- Status Bar ---
        self.status_bar = QStatusBar() # Create a QStatusBar instance
        self.setStatusBar(self.status_bar) # Set it as the main window's status bar
        self.status_bar.showMessage("Ready. Please connect to AKAI Fire.") # Initial message
        # print(f"MW DEBUG: _init_ui_layout - Status bar created and set: {self.status_bar}")
        # print("MW DEBUG: _init_ui_layout COMPLETE")

    def _create_hardware_top_strip(self) -> QGroupBox:
        from PyQt6.QtWidgets import QStackedWidget

        self.top_strip_group = QGroupBox("Device Controls");
        self.top_strip_group.setObjectName("TopStripDeviceControls");
        
        top_strip_main_layout = QHBoxLayout(self.top_strip_group);
        top_strip_main_layout.setContentsMargins(8, 0, 8, 8);
        top_strip_main_layout.setSpacing(10);
        
        knob_size = 42;
        flat_button_size = QSize(36, 10);
        icon_button_size = QSize(28, 28);
        triangle_label_style = "font-size: 9pt; color: #B0B0B0; font-weight: bold;";

        top_strip_main_layout.addStretch(1);

        # --- Knobs 1-4 ---
        knob_info_list = [
            ("knob_volume_top_right", "Global Pad Brightness"), ("knob_pan_top_right", "Pan (Unassigned)"),
            ("knob_filter_top_right", "Filter (Unassigned)"), ("knob_resonance_top_right", "Resonance (Unassigned)")
        ];          
        for attr_name, tooltip_text in knob_info_list:
            knob_stack = QStackedWidget();
            knob_stack.setFixedSize(QSize(knob_size, knob_size));
            knob_stack.setToolTip(tooltip_text); 
            static_knob_visual = StaticKnobWidget();
            knob_stack.addWidget(static_knob_visual);
            functional_dial = QDial();
            functional_dial.setFixedSize(QSize(knob_size, knob_size));
            functional_dial.setNotchesVisible(False);
            functional_dial.setWrapping(False);
            functional_dial.setObjectName(attr_name);
            functional_dial.setStyleSheet("background-color: transparent;");
            knob_stack.addWidget(functional_dial);
            if attr_name == "knob_volume_top_right": functional_dial.valueChanged.connect(self._handle_knob1_change)
            elif attr_name == "knob_pan_top_right": functional_dial.valueChanged.connect(self._handle_knob2_change)
            elif attr_name == "knob_filter_top_right": functional_dial.valueChanged.connect(self._handle_knob3_change)
            elif attr_name == "knob_resonance_top_right": functional_dial.valueChanged.connect(self._handle_knob4_change)
            top_strip_main_layout.addWidget(knob_stack, 0, Qt.AlignmentFlag.AlignCenter);
            setattr(self, attr_name, functional_dial);
            setattr(self, f"{attr_name}_visual", static_knob_visual);
            setattr(self, f"{attr_name}_stack", knob_stack);

        # --- Graphics Buttons ---
        pattern_buttons_layout = QVBoxLayout();
        pattern_buttons_layout.setSpacing(2);
        pattern_buttons_layout.setAlignment(Qt.AlignmentFlag.AlignCenter);
        triangle_up_label = QLabel("▲", styleSheet=triangle_label_style);
        triangle_up_label.setAlignment(Qt.AlignmentFlag.AlignCenter);
        self.button_pattern_up_top_right = QPushButton("");
        self.button_pattern_up_top_right.setObjectName("PatternUpButton");
        self.button_pattern_up_top_right.setFixedSize(flat_button_size);
        self.button_pattern_up_top_right.setToolTip("Cycle & Apply Next Active OLED Graphic");
        self.button_pattern_up_top_right.clicked.connect(self._handle_cycle_active_oled_next_request);
        graphics_label = QLabel("Graphics", styleSheet="font-size: 7pt; color: #777777; padding-top: 1px; padding-bottom: 1px;");
        graphics_label.setAlignment(Qt.AlignmentFlag.AlignCenter);
        self.button_pattern_down_top_right = QPushButton("");
        self.button_pattern_down_top_right.setObjectName("PatternDownButton");
        self.button_pattern_down_top_right.setFixedSize(flat_button_size);
        self.button_pattern_down_top_right.setToolTip("Cycle & Apply Previous Active OLED Graphic");
        self.button_pattern_down_top_right.clicked.connect(self._handle_cycle_active_oled_prev_request);
        triangle_down_label = QLabel("▼", styleSheet=triangle_label_style);
        triangle_down_label.setAlignment(Qt.AlignmentFlag.AlignCenter);
        for w in [triangle_up_label, self.button_pattern_up_top_right, graphics_label, self.button_pattern_down_top_right, triangle_down_label]:
            pattern_buttons_layout.addWidget(w);
        top_strip_main_layout.addLayout(pattern_buttons_layout);

        # --- OLED Display ---
        oled_container_layout = QVBoxLayout();
        oled_container_layout.setSpacing(1);
        oled_container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter);
        customize_label = QLabel("Click To Customize", styleSheet="font-size: 7pt; color: #999999; padding-bottom: 1px;");
        customize_label.setAlignment(Qt.AlignmentFlag.AlignCenter);
        self.oled_display_mirror_widget = QLabel(objectName="OLEDMirror", toolTip="Click to open OLED Customizer");
        self.oled_display_mirror_widget.setFixedSize(QSize(int(128 * 1.2), int(64 * 1.2)));
        self.oled_display_mirror_widget.setStyleSheet("QLabel#OLEDMirror { background-color: black; border: 1px solid #383838; }");
        blank_pixmap = QPixmap(self.oled_display_mirror_widget.size());
        blank_pixmap.fill(Qt.GlobalColor.black);
        self.oled_display_mirror_widget.setPixmap(blank_pixmap);
        self._setup_oled_mirror_clickable();
        oled_container_layout.addWidget(customize_label);
        oled_container_layout.addWidget(self.oled_display_mirror_widget);
        top_strip_main_layout.addLayout(oled_container_layout);

        # --- Play/Pause Icon (Created with parent, but NOT in a layout) ---
        self.oled_play_pause_icon_label = QLabel(self.top_strip_group);
        self.oled_play_pause_icon_label.setObjectName("OLEDPlayPauseIconLabel");
        self.oled_play_pause_icon_label.setToolTip("Toggle OLED Active Graphic Pause/Play");
        try:
            icon_path = get_resource_path(os.path.join("resources", "icons", "play-pause.png"));
            if os.path.exists(icon_path):
                base_pixmap = QPixmap(icon_path);
                if not base_pixmap.isNull():
                    scaled_pixmap = base_pixmap.scaled(QSize(16, 16), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation);
                    self.oled_play_pause_icon_label.setPixmap(scaled_pixmap);
                    self.oled_play_pause_icon_label.setFixedSize(scaled_pixmap.size());
        except Exception: pass;
        self.oled_play_pause_icon_label.setCursor(Qt.CursorShape.PointingHandCursor);
        self.oled_play_pause_icon_label.setEnabled(False);
        self.oled_play_pause_icon_label.installEventFilter(self);
        
        # --- Browser Button ---
        self.button_browser_top_right = QPushButton("");
        self.button_browser_top_right.setObjectName("BrowserButton");
        self.button_browser_top_right.setFixedSize(icon_button_size);
        self.button_browser_top_right.setToolTip("Sampler");
        top_strip_main_layout.addWidget(self.button_browser_top_right, 0, Qt.AlignmentFlag.AlignCenter);

        # --- Select Knob ---
        select_knob_stack = QStackedWidget();
        select_knob_stack.setFixedSize(QSize(knob_size, knob_size));
        select_knob_stack.setToolTip("Select Item / Press to Apply");
        select_knob_visual = StaticKnobWidget();
        select_knob_stack.addWidget(select_knob_visual);
        self.knob_select_top_right = QDial();
        self.knob_select_top_right.setObjectName("SelectKnobTopRight");
        self.knob_select_top_right.setFixedSize(QSize(knob_size, knob_size));
        self.knob_select_top_right.setNotchesVisible(False);
        self.knob_select_top_right.setStyleSheet("background-color: transparent;");
        select_knob_stack.addWidget(self.knob_select_top_right);
        self.knob_select_top_right.valueChanged.connect(
            lambda value, knob=select_knob_visual, qd=self.knob_select_top_right: knob.set_indicator_angle(-135 + ((value - qd.minimum()) / (qd.maximum() - qd.minimum())) * 270.0) if qd.maximum() > qd.minimum() else 0
        );
        setattr(self, "SelectKnobTopRight_visual", select_knob_visual);
        setattr(self, "SelectKnobTopRight_stack", select_knob_stack);
        top_strip_main_layout.addWidget(select_knob_stack, 0, Qt.AlignmentFlag.AlignCenter);
        
        # --- Grid Nav Buttons ---
        grid_buttons_layout = QHBoxLayout();
        grid_buttons_layout.setSpacing(1);
        triangle_left = QLabel("◀", objectName="TriangleGridLeft");
        self.button_grid_nav_focus_prev_top_right = QPushButton("", objectName="GridLeftButton", toolTip="Pad Focus (Prev)");
        self.button_grid_nav_focus_prev_top_right.setFixedSize(flat_button_size);
        self.button_grid_nav_focus_next_top_right = QPushButton("", objectName="GridRightButton", toolTip="Pad Focus (Next)");
        self.button_grid_nav_focus_next_top_right.setFixedSize(flat_button_size);
        triangle_right = QLabel("▶", objectName="TriangleGridRight");
        for w in [triangle_left, self.button_grid_nav_focus_prev_top_right, self.button_grid_nav_focus_next_top_right, triangle_right]:
            grid_buttons_layout.addWidget(w, 0, Qt.AlignmentFlag.AlignCenter);
        top_strip_main_layout.addLayout(grid_buttons_layout);
        
        top_strip_main_layout.addStretch(1);
        
        return self.top_strip_group

# In class MainWindow(QMainWindow):

    def _position_oled_toggle_icon(self):
        if not all([self.oled_play_pause_icon_label, self.oled_display_mirror_widget]):
            return

        if not self.oled_display_mirror_widget.parentWidget().isVisible():
            # Widget positions might not be calculated yet if the parent isn't visible.
            # We can try again in a moment.
            QTimer.singleShot(50, self._position_oled_toggle_icon)
            return

        # Get the position of the OLED mirror relative to its parent container
        mirror_pos = self.oled_display_mirror_widget.pos()

        # Calculate the icon's position
        icon_width = self.oled_play_pause_icon_label.width()
        icon_height = self.oled_play_pause_icon_label.height()

        # Position at bottom-right corner of the mirror widget
        target_x = mirror_pos.x() + self.oled_display_mirror_widget.width() - icon_width + 16
        target_y = mirror_pos.y() + self.oled_display_mirror_widget.height() - icon_height

        self.oled_play_pause_icon_label.move(target_x, target_y)
        self.oled_play_pause_icon_label.raise_()
        self.oled_play_pause_icon_label.show()

    def _setup_oled_mirror_clickable(self):
        """Makes the OLED mirror QLabel clickable to open the customizer."""
        if hasattr(self, 'oled_display_mirror_widget') and self.oled_display_mirror_widget:
            # To make QLabel clickable, we can install an event filter on it
            # or promote it to a custom clickable QLabel subclass.
            # Event filter is simpler for now.
            self.oled_display_mirror_widget.setToolTip(
                "Click to customize OLED display")
            self.oled_display_mirror_widget.installEventFilter(
                self)  # MainWindow will handle its events
            # print("MW TRACE: OLED mirror configured for click.")
        else:
            print(
                "MW WARNING: oled_display_mirror_widget not found during _setup_oled_mirror_clickable.")

    def _create_pad_grid_section(self) -> QWidget:
        """Creates the pad grid widget and its immediate container."""
        pad_grid_outer_container = QWidget()
        pad_grid_container_layout = QVBoxLayout(pad_grid_outer_container)
        pad_grid_container_layout.setContentsMargins(0, 0, 0, 0)
        self.pad_grid_frame = InteractivePadGridFrame(parent=self)
        pad_grid_container_layout.addWidget(
            self.pad_grid_frame, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        return pad_grid_outer_container

    def _create_midi_input_section(self) -> QGroupBox:
        """Creates the QGroupBox for MIDI Input selection."""
        input_connection_group = QGroupBox("🔌 MIDI Input (from Fire)")
        input_layout = QHBoxLayout(input_connection_group)
        self.input_port_combo_direct_ref = QComboBox()
        # print(f"DEBUG MW: _create_midi_input_section - input_port_combo ID: {id(self.input_port_combo_direct_ref)}") # Optional
        self.input_port_combo_direct_ref.setPlaceholderText(
            "Select MIDI Input")
        # input_port_combo_direct_ref.currentIndexChanged.connect(...) # Connect in _connect_signals or if specific logic needed here
        input_layout.addWidget(QLabel("Input Port:"))
        # ComboBox takes available space
        input_layout.addWidget(self.input_port_combo_direct_ref, 1)
        return input_connection_group

    def _populate_right_panel(self):
        from PyQt6.QtWidgets import QSlider, QGridLayout # Add necessary imports
        if self.right_panel_layout_v is None:
            print("MW CRITICAL ERROR: _populate_right_panel - self.right_panel_layout_v is None!")
            return
        # --- MIDI Connection Group (Output) ---
        connection_group = QGroupBox("🔌 MIDI Output")
        connection_layout = QHBoxLayout(connection_group)
        self.port_combo_direct_ref = QComboBox()
        self.port_combo_direct_ref.setPlaceholderText("Select MIDI Output")
        self.port_combo_direct_ref.currentIndexChanged.connect(self._on_port_combo_changed)
        self.connect_button_direct_ref = QPushButton("Connect")
        self.connect_button_direct_ref.clicked.connect(self.toggle_connection)
        self.connect_button_direct_ref.setEnabled(False)
        connection_layout.addWidget(QLabel("Port:"))
        connection_layout.addWidget(self.port_combo_direct_ref, 1)
        connection_layout.addWidget(self.connect_button_direct_ref)
        self.right_panel_layout_v.addWidget(connection_group)
        # --- NEW: Global Controls Group ---
        self.global_controls_group_box = QGroupBox("🔆 Global Controls")
        global_controls_layout = QGridLayout(self.global_controls_group_box)
        self.brightness_slider_label = QLabel("Brightness:")
        self.global_brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.global_brightness_slider.setRange(0, 100)
        self.global_brightness_slider.setValue(int(self.global_pad_brightness * 100))
        self.global_brightness_slider.valueChanged.connect(self._on_global_brightness_slider_changed)
        self.brightness_value_label = QLabel(f"{self.global_brightness_slider.value()}%")
        self.brightness_value_label.setMinimumWidth(40) # Reserve space
        global_controls_layout.addWidget(self.brightness_slider_label, 0, 0)
        global_controls_layout.addWidget(self.global_brightness_slider, 0, 1)
        global_controls_layout.addWidget(self.brightness_value_label, 0, 2)
        global_controls_layout.setColumnStretch(1, 1) # Make slider expand
        self.right_panel_layout_v.addWidget(self.global_controls_group_box)
        if self.color_picker_manager: self.right_panel_layout_v.addWidget(self.color_picker_manager)
        if self.static_layouts_manager: self.right_panel_layout_v.addWidget(self.static_layouts_manager)
        if self.audio_visualizer_ui_manager:
            self.audio_visualizer_ui_manager.setTitle("🎵 Audio Visualizer")
            self.right_panel_layout_v.addWidget(self.audio_visualizer_ui_manager)
        bottom_buttons_container_widget = QWidget()
        bottom_buttons_outer_layout = QVBoxLayout(bottom_buttons_container_widget)
        bottom_buttons_outer_layout.setContentsMargins(0, 10, 0, 0)
        actual_buttons_hbox = QHBoxLayout()
        actual_buttons_hbox.addStretch(1)
        self.app_guide_button = QPushButton("🚀 App Guide & Hotkey List")
        self.app_guide_button.setToolTip("Open the App Guide and Hotkey List")
        self.app_guide_button.setObjectName("AppGuideButton")
        self.app_guide_button.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.app_guide_button.clicked.connect(self._open_app_guide_dialog)
        actual_buttons_hbox.addWidget(self.app_guide_button)
        actual_buttons_hbox.addSpacing(10)
        self.button_lazy_doom = QPushButton("👹 LazyDOOM")
        self.button_lazy_doom.setToolTip("Launch the LazyDOOM on OLED experience!")
        self.button_lazy_doom.setObjectName("LazyDoomButton")
        self.button_lazy_doom.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.button_lazy_doom.clicked.connect(self._toggle_doom_mode)
        actual_buttons_hbox.addWidget(self.button_lazy_doom)
        actual_buttons_hbox.addStretch(1)
        bottom_buttons_outer_layout.addLayout(actual_buttons_hbox)
        self.right_panel_layout_v.addWidget(bottom_buttons_container_widget)
        self.right_panel_layout_v.addStretch(1)

    def _populate_left_panel(self):
        """Populates the left panel with the hardware top strip, pad grid, animator UI, and sampler UI."""
        if self.left_panel_layout is None:
            print("MW CRITICAL ERROR: _populate_left_panel - self.left_panel_layout is LITERALLY None! CANNOT POPULATE.")
            return
        # print(
        #     f"MW TRACE: _populate_left_panel - START - Layout object IS: {self.left_panel_layout} (ID: {id(self.left_panel_layout)})")
        # 1. Add Hardware Top Strip
        if hasattr(self, '_create_hardware_top_strip'):
            hardware_top_strip_widget = self._create_hardware_top_strip()
            if hardware_top_strip_widget:
                # Stretch factor 0: takes its preferred size
                self.left_panel_layout.addWidget(hardware_top_strip_widget, 0)
            else:
                print("MW WARNING: _create_hardware_top_strip did not return a widget.")
        else:
            print("MW ERROR: _create_hardware_top_strip method is missing.")
            self.left_panel_layout.addWidget(
                QLabel("Error: Hardware Top Strip Missing"))
        # 2. Add Pad Grid Section
        if hasattr(self, '_create_pad_grid_section'):
            pad_grid_container = self._create_pad_grid_section()
            if pad_grid_container:
                # Stretch factor 0: takes its preferred size
                self.left_panel_layout.addWidget(pad_grid_container, 0)
            else:
                print("MW WARNING: _create_pad_grid_section did not return a widget.")
        else:
            print("MW ERROR: _create_pad_grid_section method is missing.")
            self.left_panel_layout.addWidget(
                QLabel("Error: Pad Grid Section Missing"))
        # 3. Add AnimatorManagerWidget UI
        if self.animator_manager:
            # Stretch factor 1 (IMPORTANT)
            self.left_panel_layout.addWidget(self.animator_manager, 1)
        else:
            print(
                "MW WARNING: AnimatorManager not instantiated, cannot add its UI to left panel.")
            self.left_panel_layout.addWidget(
                QLabel("Error: Animator UI Missing"))
        # 4. Add ScreenSamplerManager UI
        if self.screen_sampler_manager:
            sampler_ui_widget = self.screen_sampler_manager.get_ui_widget()
            if sampler_ui_widget:
                # Stretch factor 0: takes its preferred size
                self.left_panel_layout.addWidget(sampler_ui_widget, 0)
            else:
                print(
                    "MW WARNING: ScreenSamplerManager UI widget (from get_ui_widget()) is None.")
                self.left_panel_layout.addWidget(
                    QLabel("Error: Sampler UI Widget Missing"))
        else:
            print(
                "MW WARNING: ScreenSamplerManager not instantiated, cannot add its UI to left panel.")
            self.left_panel_layout.addWidget(
                QLabel("Error: Sampler Manager Missing"))
        # Removed addStretch(1) to allow AnimatorManagerWidget to take all remaining space.
        # print(f"MW TRACE: _populate_left_panel - FINISHED")

# --- GROUP 3: OTHER INITIALIZATION & CONFIGURATION HELPERS ---
    def _setup_global_brightness_knob(self):
        """Configures Knob 1's initial state for global brightness."""
        if self.knob_volume_top_right:
            knob_stack = getattr(self, "knob_volume_top_right_stack", None)
            # Set tooltip on the container
            self._update_knob_tooltip_and_status(knob_stack, f"Global Pad Brightness ({int(self.global_pad_brightness * 100)}%)")
            # Set properties on the functional dial
            self.knob_volume_top_right.setRange(0, 100)
            self.knob_volume_top_right.setValue(int(self.global_pad_brightness * 100))
        else:
            print("MW WARNING: knob_volume_top_right not found during _setup_global_brightness_knob.")

    def _update_current_oled_nav_target_widget(self):
        if self.current_oled_nav_target_name == "animator":
            self.current_oled_nav_target_widget = self.animator_manager
        elif self.current_oled_nav_target_name == "static_layouts":
            self.current_oled_nav_target_widget = self.static_layouts_manager
        else:
            self.current_oled_nav_target_widget = None
        self.current_oled_nav_item_logical_index = 0
        self._oled_nav_item_count = 0
        if self.current_oled_nav_target_widget and hasattr(self.current_oled_nav_target_widget, 'get_navigation_item_count'):
            self._oled_nav_item_count = self.current_oled_nav_target_widget.get_navigation_item_count()

    def _connect_signals(self):
        # AkaiFireController raw pad/button events
        if self.akai_controller and hasattr(self.akai_controller, 'fire_button_event'):
            try: self.akai_controller.fire_button_event.disconnect(self._handle_fire_pad_event_INTERNAL)
            except TypeError: pass
            self.akai_controller.fire_button_event.connect(self._handle_fire_pad_event_INTERNAL)
        # InteractivePadGridFrame signals
        if self.pad_grid_frame:
            try: self.pad_grid_frame.pad_action_requested.disconnect(self._handle_grid_pad_action)
            except TypeError: pass
            self.pad_grid_frame.pad_action_requested.connect(self._handle_grid_pad_action)
            try: self.pad_grid_frame.pad_context_menu_requested_from_button.disconnect(self.show_pad_context_menu)
            except TypeError: pass
            self.pad_grid_frame.pad_context_menu_requested_from_button.connect(self.show_pad_context_menu)
            try: self.pad_grid_frame.pad_single_left_click_action_requested.disconnect(self._handle_grid_pad_single_left_click)
            except TypeError: pass
            self.pad_grid_frame.pad_single_left_click_action_requested.connect(self._handle_grid_pad_single_left_click)
            if self.animator_manager:
                try: self.pad_grid_frame.paint_stroke_started.disconnect(self.animator_manager.on_paint_stroke_started)
                except TypeError: pass
                self.pad_grid_frame.paint_stroke_started.connect(self.animator_manager.on_paint_stroke_started)
                try: self.pad_grid_frame.paint_stroke_ended.disconnect(self.animator_manager.on_paint_stroke_ended)
                except TypeError: pass
                self.pad_grid_frame.paint_stroke_ended.connect(self.animator_manager.on_paint_stroke_ended)
        # Color Picker Manager signals
        if self.color_picker_manager:
            try: self.color_picker_manager.final_color_selected.disconnect(self._handle_final_color_selection_from_manager)
            except TypeError: pass
            self.color_picker_manager.final_color_selected.connect(self._handle_final_color_selection_from_manager)
            try: self.color_picker_manager.status_message_requested.disconnect(self.status_bar.showMessage)
            except TypeError: pass
            self.color_picker_manager.status_message_requested.connect(self.status_bar.showMessage)
            if hasattr(self.color_picker_manager, 'request_clear_all_pads'):
                try: self.color_picker_manager.request_clear_all_pads.disconnect(self.clear_all_hardware_and_gui_pads)
                except TypeError: pass
                self.color_picker_manager.request_clear_all_pads.connect(self.clear_all_hardware_and_gui_pads)
            if hasattr(self.color_picker_manager, 'eyedropper_button_toggled'):
                try: self.color_picker_manager.eyedropper_button_toggled.disconnect(self._on_picker_eyedropper_button_toggled)
                except TypeError: pass
                self.color_picker_manager.eyedropper_button_toggled.connect(self._on_picker_eyedropper_button_toggled)
        # Static Layouts Manager signals
        if self.static_layouts_manager:
            try: self.static_layouts_manager.apply_layout_data_requested.disconnect(self._handle_apply_static_layout_data)
            except TypeError: pass
            self.static_layouts_manager.apply_layout_data_requested.connect(self._handle_apply_static_layout_data)
            try: self.static_layouts_manager.request_current_grid_colors.disconnect(self._provide_grid_colors_for_static_save)
            except TypeError: pass
            self.static_layouts_manager.request_current_grid_colors.connect(self._provide_grid_colors_for_static_save)
            try: self.static_layouts_manager.status_message_requested.disconnect(self.status_bar.showMessage)
            except TypeError: pass
            self.static_layouts_manager.status_message_requested.connect(self.status_bar.showMessage)
        # Screen Sampler Manager signals
        if self.screen_sampler_manager:
            try: self.screen_sampler_manager.sampled_colors_for_display.disconnect()
            except TypeError: pass
            self.screen_sampler_manager.sampled_colors_for_display.connect(lambda colors: self.apply_colors_to_main_pad_grid([QColor(r, g, b).name() for r, g, b in colors], update_hw=True, is_sampler_output=True))
            try: self.screen_sampler_manager.sampler_status_update.disconnect(self.status_bar.showMessage)
            except TypeError: pass
            self.screen_sampler_manager.sampler_status_update.connect(self.status_bar.showMessage)
            try: self.screen_sampler_manager.sampling_activity_changed.disconnect(self._on_sampler_activity_changed)
            except TypeError: pass
            self.screen_sampler_manager.sampling_activity_changed.connect(self._on_sampler_activity_changed)
            try: self.screen_sampler_manager.sampling_activity_changed.disconnect(self._on_sampler_activity_changed_for_knobs)
            except TypeError: pass
            self.screen_sampler_manager.sampling_activity_changed.connect(self._on_sampler_activity_changed_for_knobs)
            try: self.screen_sampler_manager.new_sequence_from_recording_ready.disconnect(self._handle_load_sequence_request)
            except TypeError: pass
            self.screen_sampler_manager.new_sequence_from_recording_ready.connect(self._handle_load_sequence_request)
            try: self.screen_sampler_manager.sampler_monitor_changed.disconnect(self._on_sampler_monitor_cycled_for_oled)
            except TypeError: pass
            self.screen_sampler_manager.sampler_monitor_changed.connect(self._on_sampler_monitor_cycled_for_oled)
            try: self.screen_sampler_manager.sampler_adjustments_changed.disconnect(self._on_sampler_adjustments_updated_for_knobs)
            except TypeError: pass
            self.screen_sampler_manager.sampler_adjustments_changed.connect(self._on_sampler_adjustments_updated_for_knobs)
        # AnimatorManagerWidget Signals
        if self.animator_manager:
            try: self.animator_manager.active_frame_data_for_display.disconnect(self._on_animator_frame_data_for_display)
            except TypeError: pass
            self.animator_manager.active_frame_data_for_display.connect(self._on_animator_frame_data_for_display)
            try: self.animator_manager.playback_status_update.disconnect(self.status_bar.showMessage)
            except TypeError: pass
            self.animator_manager.playback_status_update.connect(self.status_bar.showMessage)
            try: self.animator_manager.sequence_modified_status_changed.disconnect(self._update_oled_and_title_on_sequence_change)
            except TypeError: pass
            self.animator_manager.sequence_modified_status_changed.connect(self._update_oled_and_title_on_sequence_change)
            try: self.animator_manager.animator_playback_active_status_changed.disconnect(self._update_fire_transport_leds)
            except TypeError: pass
            self.animator_manager.animator_playback_active_status_changed.connect(self._update_fire_transport_leds)
            try: self.animator_manager.animator_playback_active_status_changed.disconnect(self._on_animator_playback_status_changed_for_knobs)
            except TypeError: pass
            self.animator_manager.animator_playback_active_status_changed.connect(self._on_animator_playback_status_changed_for_knobs)
            try: self.animator_manager.undo_redo_state_changed.disconnect(self._on_animator_undo_redo_state_changed)
            except TypeError: pass
            self.animator_manager.undo_redo_state_changed.connect(self._on_animator_undo_redo_state_changed)
            try: self.animator_manager.clipboard_state_changed.disconnect(self._on_animator_clipboard_state_changed)
            except TypeError: pass
            self.animator_manager.clipboard_state_changed.connect(self._on_animator_clipboard_state_changed)
            try: self.animator_manager.request_sampler_disable.disconnect(self._handle_request_sampler_disable)
            except TypeError: pass
            self.animator_manager.request_sampler_disable.connect(self._handle_request_sampler_disable)
            try: self.animator_manager.request_load_sequence_with_prompt.disconnect(self._handle_animator_request_load_prompt)
            except TypeError: pass
            self.animator_manager.request_load_sequence_with_prompt.connect(self._handle_animator_request_load_prompt)
        # HardwareInputManager Signals
        if self.hardware_input_manager:
            if hasattr(self.hardware_input_manager, 'physical_encoder_rotated'):
                try: self.hardware_input_manager.physical_encoder_rotated.disconnect(self._on_physical_encoder_rotated)
                except TypeError: pass
                self.hardware_input_manager.physical_encoder_rotated.connect(self._on_physical_encoder_rotated)
            if self.animator_manager:
                try: self.hardware_input_manager.request_animator_play_pause.disconnect(self.animator_manager.action_play_pause_toggle)
                except TypeError: pass
                self.hardware_input_manager.request_animator_play_pause.connect(self.animator_manager.action_play_pause_toggle)
                try: self.hardware_input_manager.request_animator_stop.disconnect(self._handle_hardware_animator_stop_request)
                except TypeError: pass
                self.hardware_input_manager.request_animator_stop.connect(self._handle_hardware_animator_stop_request)
            try: self.hardware_input_manager.grid_left_pressed.disconnect(self._handle_grid_left_pressed)
            except TypeError: pass
            self.hardware_input_manager.grid_left_pressed.connect(self._handle_grid_left_pressed)
            try: self.hardware_input_manager.grid_right_pressed.disconnect(self._handle_grid_right_pressed)
            except TypeError: pass
            self.hardware_input_manager.grid_right_pressed.connect(self._handle_grid_right_pressed)
            try: self.hardware_input_manager.select_encoder_turned.disconnect(self._handle_select_encoder_turned)
            except TypeError: pass
            self.hardware_input_manager.select_encoder_turned.connect(self._handle_select_encoder_turned)
            try: self.hardware_input_manager.select_encoder_pressed.disconnect(self._handle_select_encoder_pressed)
            except TypeError: pass
            self.hardware_input_manager.select_encoder_pressed.connect(self._handle_select_encoder_pressed)
            try: self.hardware_input_manager.request_toggle_screen_sampler.disconnect(self._on_request_toggle_screen_sampler)
            except TypeError: pass
            self.hardware_input_manager.request_toggle_screen_sampler.connect(self._on_request_toggle_screen_sampler)
            try: self.hardware_input_manager.request_cycle_sampler_monitor.disconnect(self._on_request_cycle_sampler_monitor)
            except TypeError: pass
            self.hardware_input_manager.request_cycle_sampler_monitor.connect(self._on_request_cycle_sampler_monitor)
            if hasattr(self.hardware_input_manager, 'request_cycle_active_oled_graphic_next'):
                try: self.hardware_input_manager.request_cycle_active_oled_graphic_next.disconnect(self._handle_cycle_active_oled_next_request)
                except TypeError: pass
                self.hardware_input_manager.request_cycle_active_oled_graphic_next.connect(self._handle_cycle_active_oled_next_request)
            if hasattr(self.hardware_input_manager, 'request_cycle_active_oled_graphic_prev'):
                try: self.hardware_input_manager.request_cycle_active_oled_graphic_prev.disconnect(self._handle_cycle_active_oled_prev_request)
                except TypeError: pass
                self.hardware_input_manager.request_cycle_active_oled_graphic_prev.connect(self._handle_cycle_active_oled_prev_request)
            if hasattr(self.hardware_input_manager, 'oled_browser_activate_pressed'):
                try: self.hardware_input_manager.oled_browser_activate_pressed.disconnect(self._handle_oled_browser_activate)
                except TypeError: pass
                self.hardware_input_manager.oled_browser_activate_pressed.connect(self._handle_oled_browser_activate)
        # OLEDDisplayManager Signals
        if self.oled_display_manager:
            if self.akai_controller:
                try: self.oled_display_manager.request_send_bitmap_to_fire.disconnect(self.akai_controller.oled_send_full_bitmap)
                except TypeError: pass
                self.oled_display_manager.request_send_bitmap_to_fire.connect(self.akai_controller.oled_send_full_bitmap)
            if self.oled_display_mirror_widget:
                try: self.oled_display_manager.request_send_bitmap_to_fire.disconnect(self._update_oled_mirror)
                except TypeError: pass
                self.oled_display_manager.request_send_bitmap_to_fire.connect(self._update_oled_mirror)
            if hasattr(self.oled_display_manager, 'active_graphic_pause_state_changed'):
                try: self.oled_display_manager.active_graphic_pause_state_changed.disconnect(self._update_oled_play_pause_button_ui)
                except TypeError: pass
                self.oled_display_manager.active_graphic_pause_state_changed.connect(self._update_oled_play_pause_button_ui)
        # Audio Visualizer Manager/UI Manager Signals
        if self.audio_visualizer_manager:
            try: self.audio_visualizer_manager.pad_data_ready.disconnect(self._handle_visualizer_pad_data)
            except TypeError: pass
            self.audio_visualizer_manager.pad_data_ready.connect(self._handle_visualizer_pad_data)
            try: self.audio_visualizer_manager.pad_data_ready.disconnect(self._update_gui_pads_from_visualizer)
            except TypeError: pass
            self.audio_visualizer_manager.pad_data_ready.connect(self._update_gui_pads_from_visualizer)
            try: self.audio_visualizer_manager.available_devices_updated.disconnect(self._on_visualizer_available_devices_updated)
            except TypeError: pass
            self.audio_visualizer_manager.available_devices_updated.connect(self._on_visualizer_available_devices_updated)
            try: self.audio_visualizer_manager.capture_error.disconnect(self._handle_visualizer_capture_error)
            except TypeError: pass
            self.audio_visualizer_manager.capture_error.connect(self._handle_visualizer_capture_error)
            if hasattr(self.audio_visualizer_manager, 'capture_started_signal'):
                try: self.audio_visualizer_manager.capture_started_signal.disconnect(self._on_avm_capture_started)
                except TypeError: pass
                self.audio_visualizer_manager.capture_started_signal.connect(self._on_avm_capture_started)
            if hasattr(self.audio_visualizer_manager, 'capture_stopped_signal'):
                try: self.audio_visualizer_manager.capture_stopped_signal.disconnect(self._on_avm_capture_stopped)
                except TypeError: pass
                self.audio_visualizer_manager.capture_stopped_signal.connect(self._on_avm_capture_stopped)
        if self.audio_visualizer_ui_manager:
            try: self.audio_visualizer_ui_manager.enable_visualizer_toggled.disconnect(self._handle_visualizer_toggle_request)
            except TypeError: pass
            self.audio_visualizer_ui_manager.enable_visualizer_toggled.connect(self._handle_visualizer_toggle_request)
            if self.audio_visualizer_manager:
                try: self.audio_visualizer_ui_manager.device_selection_changed.disconnect(self.audio_visualizer_manager.set_selected_device_index)
                except TypeError: pass
                self.audio_visualizer_ui_manager.device_selection_changed.connect(self.audio_visualizer_manager.set_selected_device_index)
                try: self.audio_visualizer_ui_manager.mode_selection_changed.disconnect(self.audio_visualizer_manager.update_visualization_mode)
                except TypeError: pass
                self.audio_visualizer_ui_manager.mode_selection_changed.connect(self.audio_visualizer_manager.update_visualization_mode)
            try: self.audio_visualizer_ui_manager.configure_button_clicked.disconnect(self._open_visualizer_settings_dialog)
            except TypeError: pass
            self.audio_visualizer_ui_manager.configure_button_clicked.connect(self._open_visualizer_settings_dialog)

    def _manually_position_top_strip_elements(self):
        """Calculates and sets the absolute positions of all top strip elements."""
        if not self.left_panel_widget or not self.isVisible():
            # If the parent isn't ready, try again shortly.
            QTimer.singleShot(50, self._manually_position_top_strip_elements)
            return

        # --- Define Layout Constants ---
        STRIP_HEIGHT = 90  # The total height of our top strip area
        Y_CENTER = STRIP_HEIGHT / 2
        KNOB_Y = Y_CENTER - (42 / 2) # 42 is knob_size
        LABEL_Y = KNOB_Y + 42 + 2 # Position label below the knob
        SPACING = 8 # Horizontal space between elements

        current_x = 0

        # --- Title ---
        title = self.top_strip_group.titleLabel # Use the built-in title label
        if title:
            title.move(10, 5) # Position title at top-left
            current_x = title.width() + 40 # Start after the title

        # --- Knobs 1-4 ---
        knob_attrs = ["knob_volume_top_right", "knob_pan_top_right", "knob_filter_top_right", "knob_resonance_top_right"]
        for attr in knob_attrs:
            knob_stack = getattr(self, f"{attr}_stack", None)
            knob_label = getattr(self, f"{attr}_label", None)
            if knob_stack and knob_label:
                knob_stack.move(current_x, int(KNOB_Y))
                label_width = knob_label.fontMetrics().boundingRect(knob_label.text()).width()
                label_x = current_x + (knob_stack.width() / 2) - (label_width / 2)
                knob_label.move(int(label_x), int(LABEL_Y))
                current_x += knob_stack.width() + SPACING

        # --- Graphics Buttons ---
        graphics_buttons = getattr(self, "pattern_buttons_widget", None)
        if graphics_buttons:
            graphics_buttons.move(current_x, int(Y_CENTER - graphics_buttons.height() / 2))
            current_x += graphics_buttons.width() + SPACING
        
        # --- OLED and its container ---
        oled_container = getattr(self, "oled_container_widget_ref", None)
        if oled_container:
            oled_container.move(current_x, int(Y_CENTER - oled_container.height() / 2))
            current_x += oled_container.width() + SPACING
            # Position the play/pause icon relative to the now-positioned container
            self._position_oled_toggle_icon()
        
        # --- Browser Button ---
        browser_button = getattr(self, "button_browser_top_right", None)
        if browser_button:
            browser_button.move(current_x, int(Y_CENTER - browser_button.height() / 2))
            current_x += browser_button.width() + SPACING
            
        # --- Select Knob ---
        select_knob_stack = getattr(self, "SelectKnobTopRight_stack", None)
        select_knob_label = getattr(self, "SelectKnobTopRight_label", None)
        if select_knob_stack and select_knob_label:
            select_knob_stack.move(current_x, int(KNOB_Y))
            label_width = select_knob_label.fontMetrics().boundingRect(select_knob_label.text()).width()
            label_x = current_x + (select_knob_stack.width() / 2) - (label_width / 2)
            select_knob_label.move(int(label_x), int(LABEL_Y))
            current_x += select_knob_stack.width() + SPACING

        # --- Grid Nav Buttons ---
        grid_nav_buttons = getattr(self, "grid_buttons_widget", None)
        if grid_nav_buttons:
            grid_nav_buttons.move(current_x, int(Y_CENTER - grid_nav_buttons.height() / 2))

    def _populate_visualizer_audio_devices(self):
        """
        Called on startup to populate the audio device dropdown in the visualizer UI.
        """
        if self.audio_visualizer_manager and self.audio_visualizer_ui_manager:
            # The manager's refresh_audio_devices emits available_devices_updated
            # We connect to that signal to populate the UI.
            # So, just trigger a refresh here.
            self.audio_visualizer_manager.refresh_audio_devices()
            # print("MW INFO: Requested audio device list refresh for visualizer.")
        else:
            print("MW WARNING: Audio visualizer manager/ui not ready for device population.")

    def _on_visualizer_available_devices_updated(self, devices_list: list):
        """
        Slot for AudioVisualizerManager's available_devices_updated signal.
        Populates the QComboBox in AudioVisualizerUIManager.
        """
        if self.audio_visualizer_ui_manager:
            default_device_info = None
            if self.audio_visualizer_manager: # Check if manager exists before calling
                 default_device_info = self.audio_visualizer_manager.get_default_loopback_device_info()
            
            default_idx_to_select = default_device_info['index'] if default_device_info else None
            self.audio_visualizer_ui_manager.populate_audio_devices(devices_list, default_idx_to_select)
            
            # If a default was selected, also update the logic manager
            if default_idx_to_select is not None and self.audio_visualizer_manager:
                QTimer.singleShot(0, lambda: self.audio_visualizer_manager.set_selected_device_index(default_idx_to_select))

    def _on_visualizer_enable_toggled(self, requested_enable_state: bool):
        # --- ADD THIS PRINT ---
        # print(
        #     f"MW TRACE: _on_visualizer_enable_toggled called with requested_enable_state: {requested_enable_state}, current self.is_visualizer_active: {self.is_visualizer_active}")
        import traceback
        # traceback.print_stack(limit=5) # Optional: print a short stack trace
        # --- END ADDED PRINT ---

        if not self.audio_visualizer_manager or not self.audio_visualizer_ui_manager:
            print("MW ERROR: Visualizer managers not available for enable/toggle.")
            if self.audio_visualizer_ui_manager:  # Try to reset button if managers are missing
                self.audio_visualizer_ui_manager.update_enable_button_appearance(
                    False)
            return

    # Prevent re-entry or conflicting calls if already processing a toggle
    # This is a common pattern to avoid issues with rapid signal emissions.
        # if hasattr(self, '_visualizer_toggle_in_progress') and self._visualizer_toggle_in_progress:
        #     print("MW TRACE: Visualizer toggle already in progress, ignoring call.")
        #     return
        # self._visualizer_toggle_in_progress = True

        if requested_enable_state:  # User wants to enable / UI button is now ON
            if self.is_visualizer_active:  # If app logic already thinks it's active
                # print("MW TRACE: _on_visualizer_enable_toggled(True) called, but already self.is_visualizer_active=True. Syncing button.")
                if self.audio_visualizer_ui_manager:  # Ensure button reflects true state
                    self.audio_visualizer_ui_manager.update_enable_button_appearance(
                        True)
                # self._visualizer_toggle_in_progress = False
                return

            # This is your existing print
            # print("MW DEBUG: Visualizer enabling, clearing main pad grid.")
            if self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active():
                self.screen_sampler_manager.stop_sampling_thread(emit_status=False)
            if self.animator_manager and self.animator_manager.active_sequence_model and \
                self.animator_manager.active_sequence_model.get_is_playing():
                self.animator_manager.action_stop()

            self.clear_main_pad_grid_ui(update_hw=True)

        # Attempt to start capture
        # start_capture will use _check_thread_started_status which updates self.is_capturing in AVM
        # and emits capture_error if it fails.
            self.audio_visualizer_manager.start_capture()
        # We need to wait for AVM's self.is_capturing to be set by _check_thread_started_status
        # So, we can't immediately know if it succeeded here.
        # The UI button and self.is_visualizer_active will be updated based on success/failure
        # through the capture_error signal or by directly checking AVM.is_capturing after a delay.
        # For now, let's assume it might succeed and let _handle_visualizer_capture_error fix it if not.
        # OR, a better way is to update MainWindow's state based on AVM's state after the attempt.

        # Let's defer updating MainWindow's self.is_visualizer_active and the button.
        # This will be handled by _check_thread_started_status in AVM emitting an error,
        # or if we add a success signal from AVM.
        # For now, _update_global_ui_interaction_states will query AVM.is_capturing.

        else:  # User wants to disable / UI button is now OFF
            if not self.is_visualizer_active:  # If app logic already thinks it's inactive
                # print("MW TRACE: _on_visualizer_enable_toggled(False) called, but already self.is_visualizer_active=False. Syncing button.")
                if self.audio_visualizer_ui_manager:  # Ensure button reflects true state
                    self.audio_visualizer_ui_manager.update_enable_button_appearance(
                        False)
                # self._visualizer_toggle_in_progress = False
                return

            # print("MW TRACE: Visualizer disabling logic entered.")
            if self.audio_visualizer_manager:  # Check if manager exists
                self.audio_visualizer_manager.stop_capture()
            self.is_visualizer_active = False
            self.status_bar.showMessage("Audio Visualizer Disabled.", 2000)

            if self.animator_manager and self.animator_manager.active_sequence_model:
                edit_idx = self.animator_manager.active_sequence_model.get_current_edit_frame_index()
                colors = self.animator_manager.active_sequence_model.get_frame_colors(
                    edit_idx)
                self._on_animator_frame_data_for_display(
                    colors if colors else ["#000000"] * 64)
            elif self.akai_controller and self.akai_controller.is_connected():
                self.clear_main_pad_grid_ui(update_hw=True)
    # Update button appearance based on the NEW intended state
    # This should use self.is_visualizer_active which reflects the outcome of start/stop attempt
    # However, start_capture is now async for its success check.
    # A better approach is to have AVM emit signals for capture_started and capture_stopped (or use capture_error for failed start).
    # For now, let's make it simpler: update based on requested_enable_state, and _handle_visualizer_capture_error will correct it if start fails.
        if self.audio_visualizer_ui_manager:
        # This update should reflect the action we just attempted.
        # If requested_enable_state is True, we *attempted* to start. If it fails,
        # _handle_visualizer_capture_error will call this method again with False.
            self.audio_visualizer_ui_manager.update_enable_button_appearance(
            requested_enable_state)
        # If requested_enable_state is True, we set self.is_visualizer_active to True optimistically
        # If False, we set it to False
        self.is_visualizer_active = requested_enable_state
    # This will query AVM.is_capturing for final truth
        self._update_global_ui_interaction_states()

    def _handle_visualizer_toggle_request(self, requested_to_enable: bool):
        # print(
        #     f"MW TRACE: === _handle_visualizer_toggle_request START === (Request is to enable: {requested_to_enable})")

        if self._visualizer_is_being_toggled:
        #     print(
        #         f"MW TRACE: Visualizer toggle already in progress. Request to enable '{requested_to_enable}' ignored.")
            return
        self._visualizer_is_being_toggled = True
        # print(
        #     f"MW TRACE: Set _visualizer_is_being_toggled = True. Processing request to enable: {requested_to_enable}")

        if requested_to_enable:
            if self.audio_visualizer_manager:
                if not self.audio_visualizer_manager.is_capturing:
        #             print("MW TRACE: Requesting AVM to START capture.")
                    if self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active():
                        self.screen_sampler_manager.stop_sampling_thread(
                            emit_status=False)
                    if self.animator_manager and self.animator_manager.active_sequence_model and \
                       self.animator_manager.active_sequence_model.get_is_playing():
                        self.animator_manager.action_stop()
                    self.clear_main_pad_grid_ui(update_hw=True)
                    self.audio_visualizer_manager.start_capture()
                else:
        #             print(
        #                 "MW TRACE: Request to enable, but AVM already capturing. Releasing guard.")
                    self._visualizer_is_being_toggled = False
            else:
        #         print("MW ERROR: AVM not available. Releasing guard.")
                self._visualizer_is_being_toggled = False

        else:  # requested_to_enable is False (request to disable)
            if self.audio_visualizer_manager:
                if self.audio_visualizer_manager.is_capturing:
        #             print("MW TRACE: Requesting AVM to STOP capture.")
                    self.audio_visualizer_manager.stop_capture()
                else:
        #             print(
        #                 "MW TRACE: Request to disable, but AVM already not capturing. Releasing guard.")
                    self._visualizer_is_being_toggled = False
            else:
                print("MW ERROR: AVM not available. Releasing guard.")
                self._visualizer_is_being_toggled = False

        # print(
        #     f"MW TRACE: === _handle_visualizer_toggle_request END === (Guard is: {self._visualizer_is_being_toggled})")

    def _on_avm_capture_started(self):
        # print("MW TRACE: _on_avm_capture_started slot called (AVM signaled capture has started).")
        self.is_visualizer_active = True 
        self.status_bar.showMessage("Audio Visualizer Enabled.", 2000)
        self._sync_visualizer_button_to_avm_state() # Update button to checked
        self._update_global_ui_interaction_states()
        self._visualizer_is_being_toggled = False # Release guard
        # print("MW TRACE: _on_avm_capture_started - Guard released.")

    def _on_avm_capture_stopped(self): 
        # print("MW TRACE: _on_avm_capture_stopped slot called (AVM signaled capture has stopped).")
        was_logically_active_in_mw = self.is_visualizer_active
        self.is_visualizer_active = False

        if was_logically_active_in_mw :
             self.status_bar.showMessage("Audio Visualizer Disabled.", 2000)
        
        if self.animator_manager and self.animator_manager.active_sequence_model and \
           not (self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active()):
            edit_idx = self.animator_manager.active_sequence_model.get_current_edit_frame_index()
            colors = self.animator_manager.active_sequence_model.get_frame_colors(edit_idx)
            self._on_animator_frame_data_for_display(colors if colors else ["#000000"] * 64)
        elif self.akai_controller and self.akai_controller.is_connected() and \
             not (self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active()):
            self.clear_main_pad_grid_ui(update_hw=True)

        self._sync_visualizer_button_to_avm_state() # Update button to unchecked
        self._update_global_ui_interaction_states()
        self._visualizer_is_being_toggled = False # Release guard
        # print("MW TRACE: _on_avm_capture_stopped - Guard released.")

    def _handle_visualizer_capture_error(self, error_message: str):
        # print(f"MW TRACE: _handle_visualizer_capture_error received: '{error_message}'")
        QMessageBox.warning(self, "Audio Visualizer Error", error_message)
        self.status_bar.showMessage(f"Visualizer Error: {error_message}", 5000)
        
        self.is_visualizer_active = False # Ensure MW state is false
        
        # AVM's _handle_audio_thread_error should call AVM.stop_capture(),
        # which will emit capture_stopped_signal, triggering _on_avm_capture_stopped.
        # So, _on_avm_capture_stopped will handle UI sync and guard release.
        # If AVM.stop_capture was already called, this ensures consistency.
        if self.audio_visualizer_manager and self.audio_visualizer_manager.is_capturing:
            self.audio_visualizer_manager.stop_capture() 
        else: # If AVM wasn't capturing but an error related to it occurred
            self._sync_visualizer_button_to_avm_state() # Sync button based on AVM's (now false) state
            self._update_global_ui_interaction_states()
            self._visualizer_is_being_toggled = False # Release guard here too
        #     print("MW TRACE: _handle_visualizer_capture_error - AVM not capturing, guard released directly.")

    def _sync_visualizer_button_to_avm_state(self):
        if self.audio_visualizer_ui_manager and self.audio_visualizer_manager:
            current_avm_capturing_state = self.audio_visualizer_manager.is_capturing
            self.audio_visualizer_ui_manager.update_start_stop_button_appearance(
                current_avm_capturing_state)
            if self.is_visualizer_active != current_avm_capturing_state:
                self.is_visualizer_active = current_avm_capturing_state

    def _try_start_visualizer_capture(self):
        """Attempts to start visualizer capture and updates UI based on success."""
        if self.audio_visualizer_manager.start_capture():
            self.is_visualizer_active = True
            self.status_bar.showMessage("Audio Visualizer Enabled.", 2000)
        else:
            self.is_visualizer_active = False  # Failed to start
            self.status_bar.showMessage(
                "Failed to start Audio Visualizer.", 3000)

        if self.audio_visualizer_ui_manager:
            self.audio_visualizer_ui_manager.update_enable_button_appearance(
                self.is_visualizer_active)
        self._update_global_ui_interaction_states()  # Update all UI states

    def _open_visualizer_settings_dialog(self):
        if not self.audio_visualizer_manager or not self.audio_visualizer_ui_manager:
            QMessageBox.warning(self, "Visualizer Error", "Visualizer components are not initialized.")
            return

        current_mode_key = "classic_spectrum_bars" # Default
        if self.audio_visualizer_ui_manager.visualization_mode_combo:
            # Get the mode key ('classic_spectrum_bars', 'pulse_wave_matrix', etc.)
            selected_data = self.audio_visualizer_ui_manager.visualization_mode_combo.currentData()
            if selected_data:
                current_mode_key = str(selected_data) 
        
        all_current_settings_from_manager = self.audio_visualizer_manager.get_all_mode_settings()
        
        # Prepare settings for the dialog (convert manager scale to UI scale where needed)
        settings_for_dialog = {}
        for mode_k, mode_v_manager_scale in all_current_settings_from_manager.items():
            settings_for_dialog[mode_k] = mode_v_manager_scale.copy() # Start with a copy
            
            if mode_k == "classic_spectrum_bars":
                # Sensitivity: manager (0.0-2.0) to UI (0-100)
                if "sensitivity" in settings_for_dialog[mode_k]:
                    settings_for_dialog[mode_k]["sensitivity"] = int(round(mode_v_manager_scale.get("sensitivity", 1.0) * 50.0))
                else:
                    settings_for_dialog[mode_k]["sensitivity"] = VisualizerSettingsDialog.DEFAULT_SENSITIVITY_SLIDER
                
                # Smoothing: manager (0.0-0.99) to UI (0-99)
                if "smoothing" in settings_for_dialog[mode_k]:
                    settings_for_dialog[mode_k]["smoothing"] = int(round(mode_v_manager_scale.get("smoothing", 0.2) * 100.0))
                else:
                    settings_for_dialog[mode_k]["smoothing"] = VisualizerSettingsDialog.DEFAULT_SMOOTHING_SLIDER
                
                # grow_downwards is already boolean, no conversion needed
                settings_for_dialog[mode_k].setdefault("grow_downwards", False)
                settings_for_dialog[mode_k].setdefault("band_colors", list(VisualizerSettingsDialog.DEFAULT_SPECTRUM_BAR_COLORS_HEX))

            elif mode_k == "pulse_wave_matrix":
                # Speed: manager (0.0-1.0) to UI (0-100)
                if "speed" in settings_for_dialog[mode_k]:
                    settings_for_dialog[mode_k]["speed"] = int(round(mode_v_manager_scale.get("speed", 0.5) * 100.0))
                else:
                    settings_for_dialog[mode_k]["speed"] = 50 # Default UI scale

                # Brightness Sensitivity: manager (0.0-2.0) to UI (0-100)
                if "brightness_sensitivity" in settings_for_dialog[mode_k]:
                    settings_for_dialog[mode_k]["brightness_sensitivity"] = int(round(mode_v_manager_scale.get("brightness_sensitivity", 1.0) * 50.0))
                else:
                    settings_for_dialog[mode_k]["brightness_sensitivity"] = 75 # Default UI scale
                
                settings_for_dialog[mode_k].setdefault("color", QColor("cyan").name())
            
            # Add elif for other modes as they get implemented

        dialog = VisualizerSettingsDialog(
            current_mode_key=current_mode_key, # Pass the actual current mode
            all_current_settings=settings_for_dialog, # Pass dialog-UI-scale settings
            config_save_path_func=get_user_config_file_path, # Pass the function itself
            parent=self
        )

        try: dialog.all_settings_applied.disconnect(self._handle_visualizer_settings_applied)
        except TypeError: pass # Was not connected
        dialog.all_settings_applied.connect(self._handle_visualizer_settings_applied)

        if dialog.exec():
            pass
        dialog.deleteLater()

    def _handle_visualizer_settings_applied(self, all_new_settings_from_dialog: dict):
        """
        Receives the complete settings dictionary (with UI scale values)
        from VisualizerSettingsDialog and passes it to AudioVisualizerManager,
        which will handle conversion and persistence.
        """
        # print(f"MW DEBUG: _handle_visualizer_settings_applied received (UI scale): {all_new_settings_from_dialog}")
        if not self.audio_visualizer_manager:
            print("MW ERROR: AudioVisualizerManager not available to apply settings.")
            return

        # AudioVisualizerManager's update_all_settings_from_dialog will handle
        # converting UI-scale values (e.g., sensitivity 0-100) to manager-scale (e.g., 0.0-2.0)
        # and then saving them.
        self.audio_visualizer_manager.update_all_settings_from_dialog(
            all_new_settings_from_dialog)

        self.status_bar.showMessage("Visualizer settings applied.", 2000)
        # If visualizer is active, changes in AVM should take effect.

    def _update_gui_pads_from_visualizer(self, hex_colors_list: list):
        if not self.is_visualizer_active or not self.pad_grid_frame:
            return  # Only update GUI if visualizer is active and grid exists

        if len(hex_colors_list) == 64:
            for i, hex_color_str in enumerate(hex_colors_list):
                row, col = divmod(i, 16)
                try:
                    q_color = QColor(
                        hex_color_str if hex_color_str else "#000000")
                    if not q_color.isValid():
                        q_color = QColor("#000000")
                    # update_pad_gui_color expects r, g, b integers
                    self.pad_grid_frame.update_pad_gui_color(
                        row, col, q_color.red(), q_color.green(), q_color.blue())
                except Exception as e:
                    # This might happen if hex_color_str is malformed beyond QColor's tolerance
                    # print(f"MW WARN: Error converting visualizer hex color '{hex_color_str}' for GUI pad ({row},{col}): {e}")
                    self.pad_grid_frame.update_pad_gui_color(
                        row, col, 0, 0, 0)  # Fallback to black
        # else:
            # print(f"MW WARN (_update_gui_pads_from_visualizer): Received incorrect number of colors: {len(hex_colors_list)}")

    def _handle_visualizer_pad_data(self, colors_hex_list: list):
        """
        Slot for AudioVisualizerManager's pad_data_ready signal.
        Converts hex colors to RGB tuples and sends to the Akai Fire pads.
        """
        if not (self.akai_controller and self.akai_controller.is_connected() and
                self.audio_visualizer_manager and self.audio_visualizer_manager.is_capturing):
            return

        pad_data_for_controller = []
        if len(colors_hex_list) == 64:
            for i, hex_color_str in enumerate(colors_hex_list):
                try:
                    q_color = QColor(hex_color_str if hex_color_str else "#000000")
                    if not q_color.isValid():
                        q_color = QColor("#000000")
                    pad_data_for_controller.append(
                        (i, q_color.red(), q_color.green(), q_color.blue())
                    )
                except Exception:
                    pad_data_for_controller.append((i, 0, 0, 0))
        else:
            return
        if not pad_data_for_controller:
            return

        self.akai_controller.set_multiple_pads_color(pad_data_for_controller, bypass_global_brightness=True)

    def _on_picker_eyedropper_button_toggled(self, checked: bool):
        """
        Handles the toggled signal from ColorPickerManager's eyedropper button.
        Updates MainWindow's internal eyedropper state and syncs the global QAction.
        """
        # Call the existing method that handles the logic and UI updates
        self.set_eyedropper_mode(checked) 
        
        # Ensure the global QAction for eyedropper reflects this state
        if hasattr(self, 'eyedropper_action') and self.eyedropper_action:
            if self.eyedropper_action.isChecked() != checked:
                self.eyedropper_action.setChecked(checked)

    def keyPressEvent(self, event: QKeyEvent):
        # Existing print for MW_PAD_ROUTER in _handle_fire_pad_event_INTERNAL will show routing
        # print(f"MW_KEY_PRESS: Key {event.key()}, Text '{event.text()}', isAutoRepeat: {event.isAutoRepeat()}, DOOM_ACTIVE: {self.is_doom_mode_active}") # Optional global key press debug
        if self.is_doom_mode_active and self.doom_game_controller and DOOM_MODULE_LOADED:
            doom_key_map = {
                Qt.Key.Key_W: PAD_DOOM_FORWARD, 
                Qt.Key.Key_S: PAD_DOOM_BACKWARD,
                Qt.Key.Key_A: PAD_DOOM_STRAFE_LEFT, 
                Qt.Key.Key_D: PAD_DOOM_STRAFE_RIGHT,
                Qt.Key.Key_Q: PAD_DOOM_TURN_LEFT_MAIN, 
                Qt.Key.Key_E: PAD_DOOM_TURN_RIGHT_MAIN,
                Qt.Key.Key_Left: PAD_DOOM_TURN_LEFT_ALT, 
                Qt.Key.Key_Right: PAD_DOOM_TURN_RIGHT_ALT,
                Qt.Key.Key_F: PAD_DOOM_SHOOT, 
                Qt.Key.Key_Shift: PAD_DOOM_RUN
            }
            if not event.isAutoRepeat() and event.key() in doom_key_map:
                # print(f"MW_KEY_PRESS_DOOM: Forwarding key {event.key()} to DGC as True") # DEBUG
                self.doom_game_controller.handle_pad_event(doom_key_map[event.key()], True) 
                event.accept() 
                return 
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent):
        # print(f"MW_KEY_RELEASE: Key {event.key()}, Text '{event.text()}', isAutoRepeat: {event.isAutoRepeat()}, DOOM_ACTIVE: {self.is_doom_mode_active}") # DEBUG THIS
        if self.is_doom_mode_active and self.doom_game_controller and DOOM_MODULE_LOADED:
            doom_key_map = {
                Qt.Key.Key_W: PAD_DOOM_FORWARD, 
                Qt.Key.Key_S: PAD_DOOM_BACKWARD,
                Qt.Key.Key_A: PAD_DOOM_STRAFE_LEFT, 
                Qt.Key.Key_D: PAD_DOOM_STRAFE_RIGHT,
                Qt.Key.Key_Q: PAD_DOOM_TURN_LEFT_MAIN, 
                Qt.Key.Key_E: PAD_DOOM_TURN_RIGHT_MAIN,
                Qt.Key.Key_Left: PAD_DOOM_TURN_LEFT_ALT, 
                Qt.Key.Key_Right: PAD_DOOM_TURN_RIGHT_ALT,
                Qt.Key.Key_F: PAD_DOOM_SHOOT, 
                Qt.Key.Key_Shift: PAD_DOOM_RUN
            }
            if not event.isAutoRepeat() and event.key() in doom_key_map:
                # print(f"MW_KEY_RELEASE_DOOM: Forwarding key {event.key()} to DGC as False") # DEBUG
                self.doom_game_controller.handle_pad_event(doom_key_map[event.key()], False) 
                event.accept()
                return
        super().keyReleaseEvent(event)

    def _handle_fire_pad_event_INTERNAL(self, note: int, is_pressed: bool):
        """
        Internal handler for ALL Akai Fire pad/button events from AkaiFireController.
        Routes to DOOM controller if active, otherwise handles normal app interactions
        (or delegates to HardwareInputManager for specific buttons).
        """
        # print(
            # f"MW_PAD_ROUTER: Received Note {note} (0x{note:02X}), Pressed {is_pressed}, DOOM_ACTIVE: {self.is_doom_mode_active}")
        if self.is_doom_mode_active and self.doom_game_controller:
            # print(f"MW_PAD_ROUTER: Routing to DoomGameController.") # DEBUG
            self.doom_game_controller.handle_pad_event(note, is_pressed)
            return  # Event consumed by DOOM mode
        pass  # Placeholder for non-DOOM general pad event handling if any

    def _update_oled_play_pause_button_ui(self, is_paused: bool):
        """
        Updates the OLED play/pause icon label's tooltip and icon (if needed) based on pause state.
        Ensures the label is enabled only when the controller is connected.
        """
        if not hasattr(self, 'oled_play_pause_icon_label') or not self.oled_play_pause_icon_label:
            return
        # Enable/disable based on connection state (should be handled by _update_global_ui_interaction_states)
        # But ensure here as well for robustness
        is_connected = self.akai_controller.is_connected() if hasattr(self, 'akai_controller') and self.akai_controller else False
        self.oled_play_pause_icon_label.setEnabled(is_connected)
        # Icon display logic (single icon for both states, but tooltip changes)
        icon_to_display_path = "resources/icons/play-pause.png"
        current_pixmap = self.oled_play_pause_icon_label.pixmap()
        if current_pixmap is None or current_pixmap.isNull():
            try:
                icon_path = get_resource_path(icon_to_display_path)
                if os.path.exists(icon_path):
                    base_pixmap = QPixmap(icon_path)
                    if not base_pixmap.isNull():
                        scaled_width = int(base_pixmap.width() * 0.5)
                        scaled_height = int(base_pixmap.height() * 0.5)
                        min_icon_dim = 16
                        scaled_width = max(min_icon_dim, scaled_width)
                        scaled_height = max(min_icon_dim, scaled_height)
                        scaled_pixmap = base_pixmap.scaled(
                            scaled_width, scaled_height,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
                        self.oled_play_pause_icon_label.setPixmap(scaled_pixmap)
                        if not scaled_pixmap.isNull():
                            self.oled_play_pause_icon_label.setFixedSize(scaled_pixmap.size())
                    else:
                        self.oled_play_pause_icon_label.setText("P/P")
                else:
                    self.oled_play_pause_icon_label.setText("P/P")
            except Exception:
                self.oled_play_pause_icon_label.setText("P/P")
        # Tooltip reflects the current state
        if is_paused:
            self.oled_play_pause_icon_label.setToolTip("Resume OLED Active Graphic (Click)")
        else:
            self.oled_play_pause_icon_label.setToolTip("Pause OLED Active Graphic (Click) -- fast graphic playback effects animator performance")

    def _slider_raw_value_to_fps_for_knob(self, slider_raw_value: int) -> float:
        """Converts a raw QDial/slider value (0-90) to an FPS value for Knob 4."""
        clamped_slider_val = max(MW_ANIMATOR_FPS_KNOB_MIN_SLIDER_VAL,
                                 min(slider_raw_value, MW_ANIMATOR_FPS_KNOB_MAX_SLIDER_VAL))

        if clamped_slider_val < _MW_NUM_DISCRETE_FPS_STEPS:
            return MW_FPS_MIN_DISCRETE_VALUES[clamped_slider_val]
        else:
            linear_offset_from_discrete_end = clamped_slider_val - _MW_NUM_DISCRETE_FPS_STEPS
            return MW_FPS_LINEAR_START_VALUE + linear_offset_from_discrete_end

    def _fps_to_slider_raw_value_for_knob(self, fps_value: float) -> int:
        """Converts an FPS value back to a raw QDial/slider value for Knob 4."""
        clamped_fps = max(MW_FPS_MIN_DISCRETE_VALUES[0], min(
            fps_value, MW_FPS_MAX_TARGET_VALUE))

        for i, discrete_fps in enumerate(MW_FPS_MIN_DISCRETE_VALUES):
            if abs(clamped_fps - discrete_fps) < 0.01:
                return i

        if clamped_fps >= MW_FPS_LINEAR_START_VALUE:
            slider_val = _MW_SLIDER_IDX_FOR_LINEAR_START + \
                int(round(clamped_fps - MW_FPS_LINEAR_START_VALUE))
            return max(_MW_SLIDER_IDX_FOR_LINEAR_START,
                       min(slider_val, MW_ANIMATOR_FPS_KNOB_MAX_SLIDER_VAL))

        closest_discrete_idx = 0
        min_diff = float('inf')
        for i, discrete_fps in enumerate(MW_FPS_MIN_DISCRETE_VALUES):
            diff = abs(clamped_fps - discrete_fps)
            if diff < min_diff:
                min_diff = diff
                closest_discrete_idx = i
        return closest_discrete_idx

    def _create_edit_actions(self):
        """Creates global QActions for menu items and keyboard shortcuts."""
        # Undo/Redo (Connected to AnimatorManagerWidget)
        self.undo_action = QAction("↶ Undo Sequence Edit", self)  # Icon added
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.setToolTip(
            f"Undo last sequence edit ({QKeySequence(QKeySequence.StandardKey.Undo).toString(QKeySequence.SequenceFormat.NativeText)})")
        self.undo_action.triggered.connect(self.action_animator_undo)
        self.addAction(self.undo_action) # Ensure it's added for global shortcut
        self.redo_action = QAction("↷ Redo Sequence Edit", self)  # Icon added
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.setToolTip(
            f"Redo last undone sequence edit ({QKeySequence(QKeySequence.StandardKey.Redo).toString(QKeySequence.SequenceFormat.NativeText)})")
        self.redo_action.triggered.connect(self.action_animator_redo)
        self.addAction(self.redo_action) # Ensure it's added for global shortcut
        # Animator Frame Operations (using icons from animator.controls_widget)
        self.copy_action = QAction(ICON_COPY + " Copy Frame(s)", self)
        self.copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        self.copy_action.setToolTip(
            f"Copy selected frame(s) ({QKeySequence(QKeySequence.StandardKey.Copy).toString(QKeySequence.SequenceFormat.NativeText)})")
        self.copy_action.triggered.connect(self.action_animator_copy_frames)
        self.addAction(self.copy_action)
        self.cut_action = QAction(ICON_CUT + " Cut Frame(s)", self)
        self.cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        self.cut_action.setToolTip(
            f"Cut selected frame(s) ({QKeySequence(QKeySequence.StandardKey.Cut).toString(QKeySequence.SequenceFormat.NativeText)})")
        self.cut_action.triggered.connect(self.action_animator_cut_frames)
        self.addAction(self.cut_action)
        self.paste_action = QAction(ICON_DUPLICATE + " Paste Frame(s)", self)
        self.paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        self.paste_action.setToolTip(
            f"Paste frame(s) from clipboard ({QKeySequence(QKeySequence.StandardKey.Paste).toString(QKeySequence.SequenceFormat.NativeText)})")
        self.paste_action.triggered.connect(self.action_animator_paste_frames)
        self.addAction(self.paste_action)
        self.duplicate_action = QAction(
            ICON_DUPLICATE + " Duplicate Frame(s)", self)
        self.duplicate_action.setShortcut(QKeySequence(
            Qt.Modifier.CTRL | Qt.Key.Key_D))
        self.duplicate_action.setToolTip(
            f"Duplicate selected frame(s) (Ctrl+D)")
        self.duplicate_action.triggered.connect(
            self.action_animator_duplicate_frames)
        self.addAction(self.duplicate_action)
        self.delete_action = QAction(ICON_DELETE + " Delete Frame(s)", self)
        self.delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        self.delete_action.setToolTip(f"Delete selected frame(s) (Del)")
        self.delete_action.triggered.connect(
            self.action_animator_delete_frames)
        self.addAction(self.delete_action)
        self.add_blank_global_action = QAction(
            ICON_ADD_BLANK + " Add Blank Frame", self)
        self.add_blank_global_action.setShortcut(QKeySequence(
            Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_B))
        self.add_blank_global_action.setToolTip(
            "Add a new blank frame to the current sequence (Ctrl+Shift+B).")
        self.add_blank_global_action.triggered.connect(
            self.action_animator_add_blank_frame)
        self.addAction(self.add_blank_global_action)
        # Sequence File Operations
        self.new_sequence_action = QAction("✨ New Sequence", self)
        self.new_sequence_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_sequence_action.setToolTip(
            f"Create a new animation sequence ({QKeySequence(QKeySequence.StandardKey.New).toString(QKeySequence.SequenceFormat.NativeText)})")
        self.new_sequence_action.triggered.connect(
            lambda: self.action_animator_new_sequence(prompt_save=True))
        self.addAction(self.new_sequence_action)
        self.save_sequence_as_action = QAction("💾 Save Sequence As...", self)
        self.save_sequence_as_action.setShortcut(
            QKeySequence.StandardKey.SaveAs)
        self.save_sequence_as_action.setToolTip(
            f"Save current sequence to a new file ({QKeySequence(QKeySequence.StandardKey.SaveAs).toString(QKeySequence.SequenceFormat.NativeText)})")
        self.save_sequence_as_action.triggered.connect(
            self.action_animator_save_sequence_as)
        self.addAction(self.save_sequence_as_action)
        # Eyedropper Toggle
        self.eyedropper_action = QAction("💧 Eyedropper Mode", self)
        self.eyedropper_action.setShortcut(
            QKeySequence(Qt.Key.Key_I))
        self.eyedropper_action.setToolTip(
            "Toggle Eyedropper mode to pick color from a pad (I).")
        self.eyedropper_action.setCheckable(True)
        self.eyedropper_action.triggered.connect(
            self.toggle_eyedropper_mode)
        self.addAction(self.eyedropper_action)
        # Animator Play/Pause Global Shortcut
        self.play_pause_action = QAction("Play/Pause Sequence", self)
        self.play_pause_action.setShortcut(
            QKeySequence(Qt.Key.Key_Space))
        self.play_pause_action.setToolTip(
            "Play or Pause the current animation sequence (Space).")
        self.play_pause_action.triggered.connect(
            self.action_animator_play_pause_toggle)
        self.addAction(self.play_pause_action)
        # Initial UI state update for actions (many will be disabled initially)
        self._update_global_ui_interaction_states()

    def populate_midi_ports(self):
        """Populates the MIDI output port selection QComboBox."""
        if self.port_combo_direct_ref is None:
            print("MW ERROR: Output port combo is None, cannot populate.")
            return
        # Avoid triggering changed signal during repopulation
        self.port_combo_direct_ref.blockSignals(True)
        self.port_combo_direct_ref.clear()
        ports = []
        try:
            ports = AkaiFireController.get_available_output_ports()
        except Exception as e:
            print(f"MW ERROR: Failed to get MIDI output ports: {e}")
        if ports:  # Check if list is not None and not empty
            self.port_combo_direct_ref.addItems(ports)
            self.port_combo_direct_ref.setEnabled(
                True)  # Enable if ports found
            fire_port_idx = -1
            for i, port_name in enumerate(ports):  # Find "Fire" or "Akai" port
                if isinstance(port_name, str) and \
                    ("fire" in port_name.lower() or "akai" in port_name.lower()) and \
                    "midiin" not in port_name.lower():  # Exclude input ports
                    fire_port_idx = i
                    break
            if fire_port_idx != -1:
                self.port_combo_direct_ref.setCurrentIndex(fire_port_idx)
            elif self.port_combo_direct_ref.count() > 0:  # If no Fire port, select first available
                self.port_combo_direct_ref.setCurrentIndex(0)
            # If count is 0 after attempting to add, it remains empty (handled by else below)
        if self.port_combo_direct_ref.count() == 0:  # If still empty after trying
            self.port_combo_direct_ref.addItem("No MIDI output ports found")
            self.port_combo_direct_ref.setEnabled(False)  # Disable if no ports
        self.port_combo_direct_ref.blockSignals(False)
        # Manually trigger handler for current selection to update button state
        self._on_port_combo_changed(self.port_combo_direct_ref.currentIndex())

    def populate_midi_input_ports(self):
        """
        Scans for MIDI input ports and attempts to select a default 'Akai Fire' input port.
        Stores the selected port name in self._selected_midi_input_port_name.
        This method no longer interacts with a UI ComboBox.
        """
        # print("MW DEBUG: populate_midi_input_ports (backend selection) CALLED")
        self._selected_midi_input_port_name = None # Reset
        ports = []
        try:
            ports = AkaiFireController.get_available_input_ports()
        except Exception as e:
            print(f"MW ERROR: Failed to get MIDI input ports for backend selection: {e}")
            return

        if ports:
            fire_port_name = None
            # Prioritize ports that are explicitly "Fire" and not also an output name from a common conflict
            # (e.g., some systems might list "FL STUDIO FIRE" for both input and output)
            for port_name_candidate in ports:
                if isinstance(port_name_candidate, str):
                    pn_lower = port_name_candidate.lower()
                    if "fire" in pn_lower and not any(kw in pn_lower for kw in ["midiout", "output", "kontrol"]): # Try to avoid output/other controllers
                        # More specific check if possible, e.g., "FL STUDIO FIRE 1" vs "FL STUDIO FIRE 2"
                        # This simple check is often good enough.
                        fire_port_name = port_name_candidate
                        break # Take the first good match

            if not fire_port_name: # Fallback to any "akai" if specific "fire" not found
                for port_name_candidate in ports:
                    if isinstance(port_name_candidate, str) and "akai" in port_name_candidate.lower() and \
                       not any(kw in port_name_candidate.lower() for kw in ["midiout", "output", "kontrol"]):
                        fire_port_name = port_name_candidate
                        break
            
            if fire_port_name:
                self._selected_midi_input_port_name = fire_port_name
                print(f"MW INFO: Auto-selected MIDI Input Port for backend: '{self._selected_midi_input_port_name}'")
            elif ports: # If no specific "Fire" or "Akai" port, but other ports exist, don't select one.
                print(f"MW WARNING: No specific 'Fire' or 'Akai' MIDI input port found. Found: {ports}. Input might not work automatically.")
                # Let it be None, user might have to configure manually if we add that option later.
            else:
                print("MW INFO: No MIDI input ports found at all.")
        else:
            print("MW INFO: No MIDI input ports found (get_available_input_ports returned empty).")

    def update_connection_status(self):
        """Updates UI elements based on MIDI connection state."""
        is_out_conn = self.akai_controller.is_connected() if self.akai_controller else False
        is_in_conn = self.akai_controller.is_input_connected() if self.akai_controller else False
        is_any_conn = is_out_conn or is_in_conn

        if self.connect_button_direct_ref:
            self.connect_button_direct_ref.setText("Disconnect" if is_any_conn else "Connect")
            can_attempt_connect_out = False
            if self.port_combo_direct_ref and not is_out_conn:
                current_out_text = self.port_combo_direct_ref.currentText()
                if current_out_text and current_out_text != "No MIDI output ports found":
                    can_attempt_connect_out = True
            
            # Connect button should be enabled if:
            # 1. Already connected (to allow disconnect)
            # 2. Not connected, but a valid output port is selected (to allow connect)
            self.connect_button_direct_ref.setEnabled(is_any_conn or can_attempt_connect_out)

        status_parts = []
        if is_out_conn and self.akai_controller: # Check akai_controller exists
            status_parts.append(f"Output: {self.akai_controller.port_name_used}")
        if is_in_conn and self.akai_controller: # Check akai_controller exists
            status_parts.append(f"Input: {self.akai_controller.in_port_name_used}")
        
        self.status_bar.showMessage("Connected: " + " | ".join(status_parts) if status_parts else "Disconnected.")
        
        if self.port_combo_direct_ref:
            self.port_combo_direct_ref.setEnabled(not is_out_conn)
        
        # --- REMOVED/COMMENTED OUT section for input_port_combo_direct_ref ---
        # if self.input_port_combo_direct_ref: # This UI element no longer exists
        #     self.input_port_combo_direct_ref.setEnabled(not is_in_conn)
        # --- END REMOVED/COMMENTED OUT ---
                
        if self.screen_sampler_manager:
            self.screen_sampler_manager.update_ui_for_global_state(is_out_conn, is_out_conn)
        
        # Using QTimer.singleShot to ensure UI updates happen after current event processing
        QTimer.singleShot(0, self._update_global_ui_interaction_states)

    def _update_contextual_knob_configs(self):
        sampler_is_active = self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active()
        
        dials_to_configure = [self.knob_volume_top_right, self.knob_pan_top_right, self.knob_filter_top_right, self.knob_resonance_top_right]
        for dial in dials_to_configure:
            if dial: dial.blockSignals(True)

        # Knob 1
        if self.knob_volume_top_right:
            label = getattr(self, "knob_volume_top_right_label", None)
            if label: label.setText("Brightness")
            if sampler_is_active: self.knob_volume_top_right.setRange(self.SAMPLER_BRIGHTNESS_KNOB_MIN, self.SAMPLER_BRIGHTNESS_KNOB_MAX)
            else: self.knob_volume_top_right.setRange(0, 100); self.knob_volume_top_right.setValue(int(self.global_pad_brightness * 100))

        # Knob 2
        if self.knob_pan_top_right:
            label = getattr(self, "knob_pan_top_right_label", None)
            if sampler_is_active: self.knob_pan_top_right.setRange(self.SAMPLER_SATURATION_KNOB_MIN, self.SAMPLER_SATURATION_KNOB_MAX); label.setText("Saturation") if label else None
            else: self.knob_pan_top_right.setRange(0, 127); self.knob_pan_top_right.setValue(64); label.setText("") if label else None

        # Knob 3
        if self.knob_filter_top_right:
            label = getattr(self, "knob_filter_top_right_label", None)
            if sampler_is_active: self.knob_filter_top_right.setRange(self.SAMPLER_CONTRAST_KNOB_MIN, self.SAMPLER_CONTRAST_KNOB_MAX); label.setText("Contrast") if label else None
            else: self.knob_filter_top_right.setRange(0, 127); self.knob_filter_top_right.setValue(64); label.setText("") if label else None

        # Knob 4
        if self.knob_resonance_top_right:
            label = getattr(self, "knob_resonance_top_right_label", None)
            if self.is_animator_playing and self.animator_manager:
                current_fps = self.animator_manager.get_current_sequence_fps()
                knob_raw_value = self._fps_to_slider_raw_value_for_knob(current_fps)
                self.knob_resonance_top_right.setRange(MW_ANIMATOR_FPS_KNOB_MIN_SLIDER_VAL, MW_ANIMATOR_FPS_KNOB_MAX_SLIDER_VAL); self.knob_resonance_top_right.setValue(knob_raw_value)
                if label: label.setText("Speed")
            elif sampler_is_active and self.screen_sampler_manager:
                self.knob_resonance_top_right.setRange(self.SAMPLER_HUE_KNOB_MIN, self.SAMPLER_HUE_KNOB_MAX)
                if label: label.setText("Hue")
            else:
                self.knob_resonance_top_right.setRange(0, 127); self.knob_resonance_top_right.setValue(64)
                if label: label.setText("")

        for dial in dials_to_configure:
            if dial: dial.blockSignals(False)

        self._update_all_knob_visuals()

    def _update_global_ui_interaction_states(self):
        is_connected = self.akai_controller.is_connected() if self.akai_controller else False
        is_visualizer_active_now = self.audio_visualizer_manager.is_capturing if self.audio_visualizer_manager else False
        is_sampler_active_now = self.screen_sampler_manager.is_sampling_active() if self.screen_sampler_manager else False
        is_anim_playing_now = self.animator_manager.active_sequence_model.get_is_playing() if self.animator_manager and self.animator_manager.active_sequence_model else False
        is_doom_active_now = self.is_doom_mode_active
        can_use_global_controls = is_connected and not is_visualizer_active_now and not is_sampler_active_now and not is_doom_active_now
        can_use_hardware_knobs = is_connected and not is_visualizer_active_now and not is_doom_active_now
        if hasattr(self, 'global_controls_group_box'):
            self.global_controls_group_box.setEnabled(can_use_global_controls)
        # --- DOOM Mode takes precedence ---
        if is_doom_active_now:
            if self.animator_manager: self.animator_manager.set_overall_enabled_state(False)
            if self.screen_sampler_manager: self.screen_sampler_manager.update_ui_for_global_state(False, False)
            if self.audio_visualizer_ui_manager: self.audio_visualizer_ui_manager.setEnabled(False)
            if self.pad_grid_frame: self.pad_grid_frame.setEnabled(False)
            if self.color_picker_manager: self.color_picker_manager.set_enabled(False)
            if self.static_layouts_manager: self.static_layouts_manager.set_enabled_state(False)
            if self.button_lazy_doom: self.button_lazy_doom.setEnabled(True)
            if self.app_guide_button: self.app_guide_button.setEnabled(False)
            if hasattr(self, 'global_controls_group_box'): self.global_controls_group_box.setEnabled(False)
            actions_to_disable = ['new_sequence_action', 'save_sequence_as_action', 'undo_action', 'redo_action', 'copy_action', 'cut_action', 'paste_action', 'duplicate_action', 'delete_action', 'add_blank_global_action', 'eyedropper_action', 'play_pause_action']
            for action_name in actions_to_disable:
                if hasattr(self, action_name) and getattr(self, action_name): getattr(self, action_name).setEnabled(False)
            return
        # --- Normal Mode States ---
        can_use_animator = is_connected and not is_sampler_active_now and not is_visualizer_active_now
        can_paint_direct = is_connected and not is_sampler_active_now and not is_visualizer_active_now and not is_anim_playing_now
        can_toggle_sampler = is_connected and not is_anim_playing_now and not is_visualizer_active_now
        
        if self.animator_manager: self.animator_manager.set_overall_enabled_state(can_use_animator)
        if self.screen_sampler_manager: self.screen_sampler_manager.update_ui_for_global_state(is_connected, can_toggle_sampler)
        if self.audio_visualizer_ui_manager:
            self.audio_visualizer_ui_manager.setEnabled(is_connected)
            if self.audio_visualizer_ui_manager.start_stop_button: self.audio_visualizer_ui_manager.start_stop_button.setEnabled(is_connected)
            if self.audio_visualizer_ui_manager.setup_button: self.audio_visualizer_ui_manager.setup_button.setEnabled(is_connected)
            can_change_disruptive_settings = not is_visualizer_active_now
            if hasattr(self.audio_visualizer_ui_manager, 'set_interactive_elements_enabled'): self.audio_visualizer_ui_manager.set_interactive_elements_enabled(can_change_disruptive_settings)
            
        if self.pad_grid_frame: self.pad_grid_frame.setEnabled(can_paint_direct)
        if self.color_picker_manager: self.color_picker_manager.set_enabled(can_paint_direct)
        if hasattr(self, 'eyedropper_action') and self.eyedropper_action: self.eyedropper_action.setEnabled(can_paint_direct)
        if self.static_layouts_manager: self.static_layouts_manager.set_enabled_state(can_paint_direct)
        if self.oled_play_pause_icon_label: self.oled_play_pause_icon_label.setEnabled(is_connected)
        if self.button_lazy_doom: self.button_lazy_doom.setEnabled(is_connected and not is_visualizer_active_now and not is_sampler_active_now and not is_anim_playing_now)
        if self.app_guide_button: self.app_guide_button.setEnabled(True)

# q main window init here

    def __init__(self):
        super().__init__();
        self.setWindowTitle("AKAI Fire PixelForge");
        self.setGeometry(100, 100, INITIAL_WINDOW_WIDTH, INITIAL_WINDOW_HEIGHT);
        
        # --- Assign core attributes and constants FIRST ---
        self.global_pad_brightness: float = 1.0;
        self.selected_qcolor = QColor("#04FF00");
        self.is_eyedropper_mode_active: bool = False;
        self._has_played_initial_builtin_oled_animation: bool = False;
        self.is_animator_playing: bool = False;
        self.is_visualizer_active: bool = False;
        self._visualizer_is_being_toggled: bool = False;
        self.is_doom_mode_active: bool = False;
        self._stop_action_issued_for_oled: bool = False;
        self._KNOB_FEEDBACK_OLED_DURATION_MS = 1500;
        self.current_oled_nav_target_name: str = self.OLED_NAVIGATION_FOCUS_OPTIONS[0];
        self.current_oled_nav_target_widget: QWidget | None = None;
        self.current_oled_nav_item_logical_index: int = 0;
        self._oled_nav_item_count: int = 0;
        self._oled_nav_interaction_active: bool = False;
        self._is_hardware_nav_action_in_progress: bool = False;
        self._oled_nav_debounce_timer = QTimer(self);
        self._oled_nav_debounce_timer.setSingleShot(True);
        self._oled_nav_debounce_timer.setInterval(300);

        # --- Initialize all UI element attributes to None ---
        self.central_widget_main: QWidget | None = None; self.main_app_layout: QHBoxLayout | None = None;
        self.left_panel_widget: QWidget | None = None; self.left_panel_layout: QVBoxLayout | None = None;
        self.right_panel_widget: QWidget | None = None; self.right_panel_layout_v: QVBoxLayout | None = None;
        self.top_strip_group: QGroupBox | None = None; self.global_controls_group_box: QGroupBox | None = None;
        self.knob_volume_top_right: QDial | None = None; self.knob_pan_top_right: QDial | None = None;
        self.knob_filter_top_right: QDial | None = None; self.knob_resonance_top_right: QDial | None = None;
        self.knob_select_top_right: QDial | None = None;

        # --- Set up paths BEFORE creating managers that use them ---
        if hasattr(self, '_get_presets_base_dir_path'): self.bundled_presets_base_path = self._get_presets_base_dir_path();
        else: self.bundled_presets_base_path = "error_path_bundle";
        
        self.user_documents_presets_path = get_user_documents_presets_path();
        self.user_oled_presets_base_path = os.path.join(self.user_documents_presets_path, USER_OLED_PRESETS_DIR_NAME);
        os.makedirs(self.user_oled_presets_base_path, exist_ok=True);
        self.user_oled_text_items_path = os.path.join(self.user_oled_presets_base_path, USER_OLED_TEXT_ITEMS_SUBDIR);
        os.makedirs(self.user_oled_text_items_path, exist_ok=True);
        self.user_oled_anim_items_path = os.path.join(self.user_oled_presets_base_path, USER_OLED_ANIM_ITEMS_SUBDIR);
        os.makedirs(self.user_oled_anim_items_path, exist_ok=True);
        
        # --- Scan for assets ---
        self.available_app_fonts_cache: list[str] = self._scan_available_app_fonts() if hasattr(self, '_scan_available_app_fonts') else [];
        self.active_graphic_item_relative_path: str | None = None;
        self.oled_global_scroll_delay_ms: int = DEFAULT_OLED_SCROLL_DELAY_MS_FALLBACK;
        self.current_cued_text_item_path: str | None = None;
        self.current_cued_anim_item_path: str | None = None;
        if hasattr(self, '_load_oled_config'): self._load_oled_config();
        self.available_oled_items_cache: list[dict] = [];
        if hasattr(self, '_scan_available_oled_items'): self._scan_available_oled_items();

        # --- Instantiate Core Components and Managers ---
        self.akai_controller = AkaiFireController(auto_connect=False);
        self._selected_midi_input_port_name = None;
        self.doom_game_controller = None;
        self.button_lazy_doom: QPushButton | None = None;

        self.color_picker_manager = ColorPickerManager(initial_color=self.selected_qcolor, config_save_path_func=get_user_config_file_path);
        self.static_layouts_manager = StaticLayoutsManager(user_static_layouts_path=os.path.join(self.user_documents_presets_path, "static", "user"), prefab_static_layouts_path=os.path.join(self.bundled_presets_base_path, "static", "prefab"));
        self.animator_manager = AnimatorManagerWidget(user_sequences_base_path=os.path.join(self.user_documents_presets_path, "sequences", "user"), sampler_recordings_path=os.path.join(self.user_documents_presets_path, "sequences", "sampler_recordings"), prefab_sequences_base_path=os.path.join(self.bundled_presets_base_path, "sequences", "prefab"), parent=self);
        self.screen_sampler_manager = ScreenSamplerManager(presets_base_path=self.bundled_presets_base_path, animator_manager_ref=self.animator_manager, parent=self);
        self.audio_visualizer_manager = AudioVisualizerManager(parent=self);
        self.audio_visualizer_ui_manager = AudioVisualizerUIManager(parent=self);
        
        self.oled_display_manager: OLEDDisplayManager | None = None;
        self.hardware_input_manager: HardwareInputManager | None = None;
        if self.akai_controller: 
            self.oled_display_manager = OLEDDisplayManager(akai_fire_controller_ref=self.akai_controller, available_app_fonts=self.available_app_fonts_cache, parent=self);
            self.hardware_input_manager = HardwareInputManager(akai_fire_controller_ref=self.akai_controller, parent=self);
        else: QMessageBox.critical(self, "Fatal Error", "AkaiFireController instance could not be created."); sys.exit(1);

        if self.oled_display_manager:
            self.oled_display_manager.update_global_text_item_scroll_delay(self.oled_global_scroll_delay_ms);
            self._load_and_apply_active_graphic();
            self.oled_display_manager.builtin_startup_animation_finished.connect(self._on_builtin_oled_startup_animation_finished);
        
        # --- Build UI ---
        if hasattr(self, '_set_window_icon'): self._set_window_icon();
        self.ensure_user_dirs_exist() if hasattr(self, 'ensure_user_dirs_exist') else None;
        self._init_ui_layout();
        self._populate_right_panel();
        self.left_panel_layout.addWidget(self._create_hardware_top_strip());
        self.left_panel_layout.addWidget(self._create_pad_grid_section(), 0);
        self.left_panel_layout.addWidget(self.animator_manager, 1);
        self.left_panel_layout.addWidget(self.screen_sampler_manager.get_ui_widget(), 0);

        # --- Final Setup Calls ---
        self._setup_global_brightness_knob() if hasattr(self, '_setup_global_brightness_knob') else None;
        self._update_current_oled_nav_target_widget() if hasattr(self, '_update_current_oled_nav_target_widget') else None;
        self._connect_signals() if hasattr(self, '_connect_signals') else None;
        self._create_edit_actions() if hasattr(self, '_create_edit_actions') else None;
        self.populate_midi_ports() if hasattr(self, 'populate_midi_ports') else None;
        self.populate_midi_input_ports() if hasattr(self, 'populate_midi_input_ports') else None;
        self.update_connection_status() if hasattr(self, 'update_connection_status') else None;
        
        # --- Deferred Calls ---
        QTimer.singleShot(100, self._populate_visualizer_audio_devices) if hasattr(self, '_populate_visualizer_audio_devices') else None;
        QTimer.singleShot(50, self._update_contextual_knob_configs) if hasattr(self, '_update_contextual_knob_configs') else None;
        QTimer.singleShot(100, self._position_oled_toggle_icon) if hasattr(
            self, '_position_oled_toggle_icon') else None
        QTimer.singleShot(0, self._update_global_ui_interaction_states) if hasattr(self, '_update_global_ui_interaction_states') else None;

    def eventFilter(self, obj, event: QEvent):
        # General debug (remove general print for less noise once specific object filtering works)
        # print(f"MW eventFilter: obj={type(obj).__name__} (name: {obj.objectName() if obj.objectName() else 'N/A'}), event_type={event.type()}")
        # --- Click on OLED Mirror ---
        if hasattr(self, 'oled_display_mirror_widget') and self.oled_display_mirror_widget and \
            obj == self.oled_display_mirror_widget:
            if event.type() == QEvent.Type.MouseButtonPress:
                # event IS ALREADY a QMouseEvent here
                if event.button() == Qt.MouseButton.LeftButton:  # Access button directly
                    self._open_oled_customizer_dialog()
                    return True
        # --- Click on OLED Play/Pause Icon Label ---
        if hasattr(self, 'oled_play_pause_icon_label') and self.oled_play_pause_icon_label and \
            obj == self.oled_play_pause_icon_label:
            # Only print detailed status for MouseButtonPress for this object to reduce noise
            if event.type() == QEvent.Type.MouseButtonPress:
                # print(
                    # f"MW eventFilter DEBUG: MouseButtonPress for oled_play_pause_icon_label. ObjectName: '{obj.objectName()}'")
                is_enabled_status = self.oled_play_pause_icon_label.isEnabled()
                is_visible_status = self.oled_play_pause_icon_label.isVisible()
                print(
                    f"  IconLabel Status: Enabled={is_enabled_status}, Visible={is_visible_status}, Geom={self.oled_play_pause_icon_label.geometry()}")
            if event.type() == QEvent.Type.MouseButtonPress:
                # event IS ALREADY a QMouseEvent here
                if event.button() == Qt.MouseButton.LeftButton:
                    # print("  IconLabel LeftButton clicked!") # Redundant if next print shows
                    if self.oled_play_pause_icon_label.isEnabled():
                        print(
                            "  IconLabel is ENABLED, calling _toggle_oled_active_graphic_pause...")
                        self._toggle_oled_active_graphic_pause()
                        return True
                    else:
                        print("  IconLabel is DISABLED, click ignored.")
                        return True
        return super().eventFilter(obj, event)

    def _on_oled_global_settings_changed(self,
                                        new_active_graphic_item_path: str | None,
                                        new_global_scroll_delay_ms: int):
        """
        Called when OLEDCustomizerDialog emits global_settings_changed.
        Updates MainWindow's state, saves config, and re-applies Active Graphic.
        """
        # print(
        #     f"MW INFO: OLED global settings changed. New Active Graphic path: '{new_active_graphic_item_path}', Scroll delay: {new_global_scroll_delay_ms}ms")
        self.active_graphic_item_relative_path = new_active_graphic_item_path
        self.oled_global_scroll_delay_ms = new_global_scroll_delay_ms
        self._save_oled_config()  # Save new settings
        if self.oled_display_manager:
            # Update global scroll speed for text items in OLEDDisplayManager
            self.oled_display_manager.update_global_text_item_scroll_delay(
                self.oled_global_scroll_delay_ms)
            # Reload and apply the (potentially new) Active Graphic
            self._load_and_apply_active_graphic()  # This calls set_active_graphic on ODM
        self._scan_available_oled_items()  # Refresh library cache

    def _toggle_doom_mode(self):
        if not DOOM_MODULE_LOADED: # Check if the module actually loaded
            QMessageBox.warning(self, "Feature Unavailable", 
                                "LazyDOOM module could not be loaded. Please check console for errors.")
            if self.button_lazy_doom: self.button_lazy_doom.setEnabled(False) # Disable button if module fails
            return
        if self.is_doom_mode_active:
            self._exit_doom_mode()
        else:
            self._enter_doom_mode()

    def _enter_doom_mode(self):
        print("MW INFO: Attempting to enter LazyDOOM mode...")
        if not self.akai_controller or not self.akai_controller.is_connected():
            QMessageBox.warning(self, "DOOM Mode Error", "Akai Fire is not connected. Please connect first.")
            return
        instructions_dialog = DoomInstructionsDialog(self)
        dialog_result = instructions_dialog.exec()
        selected_difficulty = instructions_dialog.get_selected_difficulty() # Get difficulty
        instructions_dialog.deleteLater() 
        if dialog_result != QDialog.DialogCode.Accepted:
            print("MW INFO: LazyDOOM cancelled by user from instructions dialog.")
            return 
        print(f"MW INFO: Proceeding to enter DOOM mode. Selected Difficulty: {selected_difficulty}")
        self.is_doom_mode_active = True
        # Disable Conflicting Features (as before)
        if self.animator_manager:
            if self.animator_manager.active_sequence_model and self.animator_manager.active_sequence_model.get_is_playing():
                self.animator_manager.action_stop() 
            if hasattr(self.animator_manager, 'set_interactive'): self.animator_manager.set_interactive(False)
            else: self.animator_manager.setEnabled(False)
        if self.screen_sampler_manager:
            if self.screen_sampler_manager.is_sampling_active(): self.screen_sampler_manager.stop_sampling_thread()
            if hasattr(self.screen_sampler_manager, 'set_interactive'): self.screen_sampler_manager.set_interactive(False)
            elif self.screen_sampler_manager.get_ui_widget(): self.screen_sampler_manager.get_ui_widget().setEnabled(False)
        if self.static_layouts_manager:
            if hasattr(self.static_layouts_manager, 'set_interactive'): self.static_layouts_manager.set_interactive(False)
            else: self.static_layouts_manager.setEnabled(False) 
        if self.color_picker_manager: self.color_picker_manager.setEnabled(False)
        if self.pad_grid_frame: self.pad_grid_frame.setEnabled(False) 
        if hasattr(self, 'quick_tools_group_ref') and self.quick_tools_group_ref: self.quick_tools_group_ref.setEnabled(False)
        if self.oled_display_manager: self.oled_display_manager.begin_external_oled_override()
        try:
            if self.doom_game_controller is not None:
                self.doom_game_controller.stop_game(); self.doom_game_controller.deleteLater(); self.doom_game_controller = None
            # --- Pass selected_difficulty to DoomGameController ---
            self.doom_game_controller = DoomGameController(self.akai_controller, 
                                                            initial_difficulty_level=selected_difficulty, 
                                                            parent=self)
            self.doom_game_controller.frame_ready_for_oled_signal.connect(self._handle_doom_frame_for_display)
            self.doom_game_controller.game_over_signal.connect(self._handle_doom_game_over)
            self.doom_game_controller.start_game() # DGC.start_game() now uses its stored difficulty
            print("MW INFO: DoomGameController started successfully.")
        except Exception as e_dgc:
            print(f"MW CRITICAL: Failed to initialize or start DoomGameController: {e_dgc}")
            import traceback; traceback.print_exc()
            QMessageBox.critical(self, "DOOM Error", f"Could not start LazyDOOM: {e_dgc}")
            self._exit_doom_mode(); return
        if self.button_lazy_doom: self.button_lazy_doom.setText("⏪ Exit LazyDOOM")
        self.status_bar.showMessage(f"LazyDOOM Mode Active! ({selected_difficulty}) 👹", 0) 
        self._update_global_ui_interaction_states() 

    def _exit_doom_mode(self):
        print("MW INFO: Exiting LazyDOOM mode...")

        # 1. Stop DOOM (if active)
        if self.doom_game_controller:
            print("MW INFO: Stopping DoomGameController...")
            self.doom_game_controller.stop_game()

            try:
                self.doom_game_controller.frame_ready_for_oled_signal.disconnect(
                    self._handle_doom_frame_for_display)
                self.doom_game_controller.game_over_signal.disconnect(
                    self._handle_doom_game_over)
            except TypeError:
                # print("MW INFO: Signals for DoomGameController were not connected or already disconnected (during exit).") # Optional
                pass
            except Exception as e_disconnect:
                print(
                    f"MW WARNING: Error disconnecting DoomGameController signals during exit: {e_disconnect}")

            self.doom_game_controller.deleteLater()
            self.doom_game_controller = None
            print("MW INFO: DoomGameController stopped and cleaned up.")

        self.is_doom_mode_active = False

        # 2. OLED Control
        if self.oled_display_manager:
            self.oled_display_manager.end_external_oled_override()
            print("MW INFO: OLEDDisplayManager external override ended.")

        # 3. Re-enable Conflicting Features
        if self.animator_manager:
            if hasattr(self.animator_manager, 'set_interactive'):
                self.animator_manager.set_interactive(True)
            else:
                self.animator_manager.setEnabled(True)
            print("MW INFO: Animator re-enabled.")

        if self.screen_sampler_manager:
            if hasattr(self.screen_sampler_manager, 'set_interactive'):
                self.screen_sampler_manager.set_interactive(True)
            elif self.screen_sampler_manager.get_ui_widget():
                self.screen_sampler_manager.get_ui_widget().setEnabled(True)
            print("MW INFO: Screen Sampler re-enabled.")

        if self.static_layouts_manager:
            if hasattr(self.static_layouts_manager, 'set_interactive'):
                self.static_layouts_manager.set_interactive(True)
            else:
                self.static_layouts_manager.setEnabled(True)
            print("MW INFO: Static Layouts re-enabled.")

        if self.color_picker_manager:
            self.color_picker_manager.setEnabled(True)
            print("MW INFO: Color Picker re-enabled.")

        if self.pad_grid_frame:
            self.pad_grid_frame.setEnabled(True)
            print("MW INFO: Pad Grid Frame re-enabled.")

        if hasattr(self, 'quick_tools_group_ref') and self.quick_tools_group_ref:
            self.quick_tools_group_ref.setEnabled(True)
            print("MW INFO: Quick Tools re-enabled.")

        # 4. Restore Main App Pad Lights
        if self.akai_controller and self.akai_controller.is_connected():
            if self.animator_manager and self.animator_manager.active_sequence_model:
                print("MW INFO: Attempting to restore animator pad display...")
                try:
                    # --- THIS IS THE CORRECTED LOGIC ---
                    current_edit_index = self.animator_manager.active_sequence_model.get_current_edit_frame_index()
                    if current_edit_index >= 0:  # Ensure index is valid
                        current_frame_colors = self.animator_manager.active_sequence_model.get_frame_colors(
                            current_edit_index)
                        if current_frame_colors:
                            self.apply_colors_to_main_pad_grid(
                                current_frame_colors, update_hw=True, is_sampler_output=False)
                            print(
                                f"MW INFO: Restored animator frame {current_edit_index} to pads.")
                        else:
                            print(
                                f"MW WARNING: No colors returned for animator frame {current_edit_index}, clearing pads.")
                            self.akai_controller.clear_all_pads()
                    else:
                        print(
                            "MW INFO: No valid current edit frame in animator, clearing pads.")
                        self.akai_controller.clear_all_pads()
                    # --- END CORRECTION ---
                except AttributeError as e_attr:  # Catch if methods are still named differently
                    print(
                        f"MW ERROR: AttributeError restoring animator pad state: {e_attr}. Check SequenceModel method names (e.g., get_current_edit_frame_index, get_frame_colors).")
                    self.akai_controller.clear_all_pads()
                except Exception as e_restore_anim:
                    print(
                        f"MW WARNING: Generic error restoring animator pad state on DOOM exit: {e_restore_anim}")
                    self.akai_controller.clear_all_pads()
            elif self.akai_controller and self.akai_controller.is_connected():
                print(
                    "MW INFO: No active animator sequence, clearing pads on DOOM exit.")
                self.akai_controller.clear_all_pads()

        if self.button_lazy_doom:
            self.button_lazy_doom.setText("👹 LazyDOOM")
        self.status_bar.showMessage("Ready.", 0)
        self._update_global_ui_interaction_states()
        print("MW INFO: LazyDOOM mode exited completely.")

    def _handle_doom_frame_for_display(self, packed_frame: bytes): # Slot expects bytes
        if not self.is_doom_mode_active: 
            return
        # --- ADDED CHECK ---
        if packed_frame is None:
            print("MW_DEBUG_DOOM_FRAME: Received None for packed_frame. Not sending to controller or mirror.")
            return
        if not isinstance(packed_frame, bytes):
            print(f"MW_DEBUG_DOOM_FRAME: Received packed_frame of wrong type: {type(packed_frame)}. Expected bytes.")
            return
        if len(packed_frame) != 1176: # Assuming PACKED_BITMAP_SIZE_BYTES is 1176
            print(f"MW_DEBUG_DOOM_FRAME: Received packed_frame with incorrect length: {len(packed_frame)}. Expected 1176.")
            # Optionally, still try to send to mirror if you want to see what unpacking does with it
            # self._update_oled_mirror(packed_frame) # Risky if length is wrong for unpacker
            return 
        if self.akai_controller and self.akai_controller.is_connected():
            self.akai_controller.oled_send_full_bitmap(packed_frame) # This is where the error was seen
        if hasattr(self, '_update_oled_mirror'):
            self._update_oled_mirror(packed_frame)

    def _handle_doom_game_over(self, message: str, is_win: bool):
        """
        Slot for DoomGameController's game_over_signal.
        Handles MainWindow's response to the game ending, primarily by updating the status bar.
        The OLED display and restart prompt are managed by DoomGameController.
        """
        if not self.is_doom_mode_active: 
            print("MW WARNING: _handle_doom_game_over called when DOOM mode not active. Ignoring.")
            return
        print(f"MW: DOOM Game Over received! Message: '{message}', Win: {is_win}")
        # Update MainWindow's status bar with the game result for a few seconds.
        self.status_bar.showMessage(f"LazyDOOM: {message}", 7000) 
        if is_win:
            print("MW: Player WON LazyDOOM!")
            pass 
        else: # Player lost
            print(f"MW: Player lost LazyDOOM.")
            pass # MainWindow acknowledges the loss.

    def _open_oled_customizer_dialog(self):
        self._scan_available_oled_items()
        dialog = OLEDCustomizerDialog(
            current_active_graphic_path=self.active_graphic_item_relative_path,  # <<< CHANGED KEYWORD
            current_global_scroll_delay_ms=self.oled_global_scroll_delay_ms,
            available_oled_items=self.available_oled_items_cache,
            user_oled_presets_base_path=self.user_oled_presets_base_path,
            available_app_fonts=self.available_app_fonts_cache,
            parent=self
        )
        try:
            dialog.global_settings_changed.disconnect(self._on_oled_global_settings_changed)
        except TypeError:
            pass
        dialog.global_settings_changed.connect(self._on_oled_global_settings_changed)
        if dialog.exec():
            pass
        else:
            pass
        dialog.deleteLater()

    def _initial_knob_setup_based_on_sampler_state(self):
        """Called shortly after startup to set initial knob configs."""
        if self.screen_sampler_manager:
            self._on_sampler_activity_changed_for_knobs(self.screen_sampler_manager.is_sampling_active())
        else:
            self._on_sampler_activity_changed_for_knobs(False) # Default to global mode

    def _revert_oled_after_knob_feedback(self):
        """
        Called by the _oled_knob_feedback_timer timeout.
        Tells OLEDDisplayManager to restore its display after knob feedback.
        """
        if self.oled_display_manager:
            # print(f"MW TRACE: Reverting OLED from knob feedback.") # Optional
            self.oled_display_manager.revert_after_knob_feedback()
        # _oled_previous_intended_text is now managed within OLEDDisplayManager if needed,
        # or simply by its state logic. MainWindow doesn't need to store it.
        # Let's remove self._oled_previous_intended_text attribute from MainWindow.
        # The OLEDDisplayManager.get_current_intended_display_text() is what matters before showing knob value.

    def _show_knob_feedback_on_oled(self, feedback_text: str):
        """
        Displays temporary knob feedback on the OLED using OLEDDisplayManager's
        show_system_message method. This message will use TomThumb 60pt by default.
        """
        if self.oled_display_manager:
            # print(f"MW TRACE: Requesting OLED feedback: '{feedback_text}'") # Optional debug
            self.oled_display_manager.show_system_message(
                text=feedback_text,
                duration_ms=self._KNOB_FEEDBACK_OLED_DURATION_MS,
                scroll_if_needed=False
            )
            # The _oled_knob_feedback_timer and _revert_oled_after_knob_feedback
            # are no longer needed in MainWindow, as OLEDDisplayManager.show_system_message
            # handles its own timed revert mechanism internally.
        else:
            print(
                "MW WARNING: OLEDDisplayManager not available for _show_knob_feedback_on_oled.")

    def _update_oled_and_title_on_sequence_change(self, is_modified: bool, sequence_name: str | None):
        """
        Updates the main window title and shows the sequence name/status
        as a temporary message on the OLED display.
        Shows a brief "New*" or "New Seq*" for newly created, unnamed sequences.
        """
        base_title = "AKAI Fire PixelForge" # <<< Assuming you've updated your app name
        effective_title_name = "Untitled" # Default for title bar
        if sequence_name and sequence_name.strip() and sequence_name.lower() != "new sequence":
            effective_title_name = sequence_name
        
        title = f"{base_title} - {effective_title_name}"
        if is_modified:
            title += "*"
        self.setWindowTitle(title)
        if self.oled_display_manager:
            oled_message_text = None
            duration_ms = 2000  # Default duration
            scroll_needed = True # Default scroll behavior
            if sequence_name and sequence_name.lower() == "new sequence":
                oled_message_text = "New Seq" # Or just "New"
                if is_modified: # Usually a new sequence becomes modified quickly
                    oled_message_text += "*"
                duration_ms = 1200  # Shorter duration for this quick cue
                scroll_needed = False # "New Seq*" is short, no scroll needed
            elif sequence_name and sequence_name.strip(): # Existing named sequence
                oled_message_text = f"Seq: {sequence_name}"
                if is_modified:
                    oled_message_text += "*"
            elif self.animator_manager and self.animator_manager.active_sequence_model: 
                # Has a model, but no specific name (should be caught by "New Sequence" above if that's the name)
                # This case now primarily handles if sequence_name is None or empty string but model exists
                oled_message_text = "Seq: Untitled"
                if is_modified:
                    oled_message_text += "*"
            if oled_message_text:
                self.oled_display_manager.show_system_message(
                    text=oled_message_text,
                    duration_ms=duration_ms,
                    scroll_if_needed=scroll_needed
                )
            elif self.oled_display_manager._active_graphic_item_type != "image_animation" and \
                not self.oled_display_manager.is_active_graphic_paused(): # Check if not paused
                self.oled_display_manager.set_active_graphic( # This re-evaluates and plays
                    self.oled_display_manager._active_graphic_item_data
                )

    def _cycle_and_apply_active_oled(self, direction: int):
        if not self.akai_controller or not self.akai_controller.is_connected():
            self.status_bar.showMessage("Connect to Akai Fire first.", 2000)
            return

        if not hasattr(self, 'available_oled_items_cache') or not self.available_oled_items_cache:
            # No items available, so nothing to display on OLED other than perhaps a blank screen
            # or let OLEDDisplayManager handle its default if no active graphic is set.
            # If you want to explicitly clear it:
            # if self.oled_display_manager:
            #     self.oled_display_manager.set_active_graphic(None) # This would show app default
            self.status_bar.showMessage("No OLED items available to cycle.", 2000)
            return

        num_items = len(self.available_oled_items_cache)
        current_idx = -1

        if self.active_graphic_item_relative_path:
            try:
                current_path_norm = self.active_graphic_item_relative_path.replace(os.path.sep, '/')
                current_idx = [
                    item['relative_path'].replace(os.path.sep, '/') for item in self.available_oled_items_cache
                ].index(current_path_norm)
            except ValueError:
                current_idx = -1 
        
        if current_idx == -1: 
            if direction == 1: 
                new_idx = 0 if num_items > 0 else -1 
            else: 
                new_idx = num_items - 1 if num_items > 0 else -1
        else:
            new_idx = (current_idx + direction + num_items) % num_items
        
        if new_idx == -1: 
            self.status_bar.showMessage("No OLED items available to cycle.", 2000)
            # If you want to clear the active graphic if list becomes empty / no valid index:
            # if self.oled_display_manager:
            #    self.oled_display_manager.set_active_graphic(None)
            # self.active_graphic_item_relative_path = None
            # self._save_oled_config()
            return

        new_item_to_activate = self.available_oled_items_cache[new_idx]
        new_relative_path = new_item_to_activate['relative_path']
        
        full_item_data = self._load_oled_item_data(new_relative_path)

        if full_item_data:
            self.active_graphic_item_relative_path = new_relative_path
            if self.oled_display_manager:
                # Directly set the new active graphic. No temporary text feedback on OLED.
                self.oled_display_manager.set_active_graphic(full_item_data)
            
            self._save_oled_config() 
            self.status_bar.showMessage(f"OLED Active: {new_item_to_activate['name']}", 2500) # Status bar feedback is still useful
        else:
            self.status_bar.showMessage(f"Error loading OLED item: {new_item_to_activate['name']}", 3000)

    def _handle_cycle_active_oled_next_request(self):
        # print("MW TRACE: _handle_cycle_active_oled_next_request called") # Optional
        self._cycle_and_apply_active_oled(1)

    def _handle_cycle_active_oled_prev_request(self):
        # print("MW TRACE: _handle_cycle_active_oled_prev_request called") # Optional
        self._cycle_and_apply_active_oled(-1)

    def _init_animator_and_sampler_ui_left_panel(self):
        """Initializes and adds Animator and Screen Sampler UIs to the left panel."""
        self.animator_manager = AnimatorManagerWidget(
            user_sequences_base_path=os.path.join(self.user_documents_presets_path, "sequences", "user"),
            sampler_recordings_path=os.path.join(self.user_documents_presets_path, "sequences", "sampler_recordings"),
            prefab_sequences_base_path=os.path.join(self.bundled_presets_base_path, "sequences", "prefab"),
            parent=self # Pass parent if AnimatorManagerWidget is QWidget
        )
        self.left_panel_layout.addWidget(self.animator_manager) # Add to left panel
        # --- ScreenSamplerManager ---
        self.screen_sampler_manager = ScreenSamplerManager( 
            presets_base_path=self.bundled_presets_base_path, # For potential future sampler prefabs
            animator_manager_ref=self.animator_manager, # For saving recordings
            parent=self # Pass parent if ScreenSamplerManager is QObject/QWidget based for its UI
        )
        self.left_panel_layout.addWidget(self.screen_sampler_manager.get_ui_widget()) # Add its UI part        
        self.left_panel_layout.addStretch(1) # Push animator/sampler UI up if space allows

    def _provide_grid_colors_for_static_save(self):
        """
        Handles the request_current_grid_colors signal from StaticLayoutsManager.
        Provides the current colors from the main pad grid to the manager for saving.
        """
        if self.static_layouts_manager and self.pad_grid_frame:
            current_colors_hex = self.pad_grid_frame.get_current_grid_colors_hex()
            # Tell StaticLayoutsManager to proceed with saving these colors
            # The StaticLayoutsManager will then handle the "Save As" dialog.
            self.static_layouts_manager.save_layout_with_colors(current_colors_hex)
            # print(f"MW DEBUG: Provided grid colors to StaticLayoutsManager for saving.") # Optional
        else: # Optional
            if self.status_bar:
                self.status_bar.showMessage("Cannot save layout: UI components missing or not ready.", 3000)

    def _handle_apply_static_layout_data(self, colors_hex: list):
        """
        Handles the apply_layout_data_requested signal from StaticLayoutsManager.
        Applies the given color data to the main pad grid and hardware.
        Also updates the current animator frame if an animator sequence is active.
        """
        if not self.akai_controller or not self.akai_controller.is_connected():
            self.status_bar.showMessage("Connect to Akai Fire first to apply layout.", 2500)
            return
        # Stop any ongoing processes like sampler or animator playback
        if self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active():
            self.screen_sampler_manager.stop_sampling_thread()
            self.status_bar.showMessage("Sampler stopped by applying static layout.", 2000)       
        if self.animator_manager and self.animator_manager.active_sequence_model and \
            self.animator_manager.active_sequence_model.get_is_playing():
            self.animator_manager.action_stop() # Stop animator playback
            self.status_bar.showMessage("Animation stopped by applying static layout.", 2000)
        self.apply_colors_to_main_pad_grid(colors_hex, update_hw=True, is_sampler_output=False)        
        if self.animator_manager and self.animator_manager.active_sequence_model:
            self.animator_manager.active_sequence_model.update_all_pads_in_current_edit_frame(colors_hex)
            self.status_bar.showMessage("Static layout applied to pads and current animator frame.", 2500)
        else:
            self.status_bar.showMessage("Static layout applied to pads.", 2500)    

    def _update_knob_tooltip_and_status(self, knob_stack_widget: QWidget | None, tooltip_text: str, status_message: str | None = None):
        """Helper to update a knob's tooltip and optionally post a status bar message."""
        if knob_stack_widget:
            knob_stack_widget.setToolTip(tooltip_text)
        if status_message:
            self.status_bar.showMessage(status_message, 4000) # Show for 4 seconds

    def _on_physical_encoder_rotated(self, encoder_id: int, delta: int):
        if self.is_visualizer_active:
            return

        target_knob: QDial | None = None
        if encoder_id == 1: target_knob = self.knob_volume_top_right
        elif encoder_id == 2: target_knob = self.knob_pan_top_right
        elif encoder_id == 3: target_knob = self.knob_filter_top_right
        elif encoder_id == 4: target_knob = self.knob_resonance_top_right
        
        if not target_knob:
            return

        step: int = 0
        sampler_is_currently_active = self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active()
        animator_is_currently_playing = self.is_animator_playing

        if encoder_id == 1:
            step = self.SAMPLER_FACTOR_KNOB_STEP if sampler_is_currently_active else self.GLOBAL_BRIGHTNESS_KNOB_STEP
        elif encoder_id in [2, 3] and sampler_is_currently_active:
            step = self.SAMPLER_FACTOR_KNOB_STEP
        elif encoder_id == 4:
            if animator_is_currently_playing: step = self.ANIMATOR_SPEED_KNOB_STEP
            elif sampler_is_currently_active: step = self.SAMPLER_HUE_KNOB_STEP
        
        if step != 0:
            current_gui_value = target_knob.value()
            new_gui_value = current_gui_value + (delta * step)
            new_gui_value = max(target_knob.minimum(), min(new_gui_value, target_knob.maximum()))

            if new_gui_value != current_gui_value:
                target_knob.setValue(new_gui_value)

    def _update_all_knob_visuals(self):
        """Helper to force-update all visual knobs to match their functional counterparts' values."""
        knob_attr_names = ["knob_volume_top_right", "knob_pan_top_right", "knob_filter_top_right", "knob_resonance_top_right", "SelectKnobTopRight"]
        for attr_name in knob_attr_names:
            qdial = getattr(self, attr_name, None)
            visual_knob = getattr(self, f"{attr_name}_visual", None)
            if qdial and visual_knob:
                min_val, max_val, current_val = qdial.minimum(), qdial.maximum(), qdial.value()
                if max_val > min_val:
                    angle = -135 + ((current_val - min_val) / (max_val - min_val)) * 270.0
                    visual_knob.set_indicator_angle(angle)

    def _on_sampler_activity_changed_for_knobs(self, sampler_is_active: bool):
        if sampler_is_active:
            self.status_bar.showMessage("Knobs now control Sampler: Brightness, Saturation, Contrast, Hue", 4000)
        else:
            self.status_bar.showMessage("Knobs reverted to Global / Animator context.", 4000)
        self._update_contextual_knob_configs()

    def _on_sampler_adjustments_updated_for_knobs(self, adjustments: dict):
        if not (self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active()):
            return 
        if self.knob_volume_top_right:
            self.knob_volume_top_right.blockSignals(True)
            brightness_factor = adjustments.get('brightness', 1.0)
            self.knob_volume_top_right.setValue(int(round(brightness_factor * 100)))
            self.knob_volume_top_right.setToolTip(f"Sampler: Brightness ({brightness_factor:.2f}x)")
            self.knob_volume_top_right.blockSignals(False)
        if self.knob_pan_top_right:
            self.knob_pan_top_right.blockSignals(True)
            saturation_factor = adjustments.get('saturation', 1.0)
            self.knob_pan_top_right.setValue(int(round(saturation_factor * 100)))
            self.knob_pan_top_right.setToolTip(f"Sampler: Saturation ({saturation_factor:.2f}x)")
            self.knob_pan_top_right.blockSignals(False)
        if self.knob_filter_top_right:
            self.knob_filter_top_right.blockSignals(True)
            contrast_factor = adjustments.get('contrast', 1.0)
            self.knob_filter_top_right.setValue(int(round(contrast_factor * 100)))
            self.knob_filter_top_right.setToolTip(f"Sampler: Contrast ({contrast_factor:.2f}x)")
            self.knob_filter_top_right.blockSignals(False)
        if self.knob_resonance_top_right: 
            self.knob_resonance_top_right.blockSignals(True)
            hue_val = int(round(adjustments.get('hue_shift', 0)))
            self.knob_resonance_top_right.setValue(hue_val)
            self.knob_resonance_top_right.setToolTip(f"Sampler: Hue Shift ({hue_val:+d})")
            self.knob_resonance_top_right.blockSignals(False)
        self._update_all_knob_visuals()

    def _on_animator_speed_knob_changed(self, knob_raw_slider_value: int):
        if self.is_animator_playing and self.animator_manager:
            new_fps = self._slider_raw_value_to_fps_for_knob(knob_raw_slider_value)
            self.animator_manager.set_playback_fps(new_fps)
            if self.knob_resonance_top_right:
                self.knob_resonance_top_right.setToolTip(f"Anim Speed: {new_fps:.1f} FPS")
            oled_feedback_text = f"Spd: {new_fps:.1f}"
            self._show_knob_feedback_on_oled(oled_feedback_text)

    def _on_animator_playback_status_changed_for_knobs(self, is_playing: bool):
        self.is_animator_playing = is_playing
        if is_playing:
            self.status_bar.showMessage("Knob 4 now controls Animation Speed (FPS).", 4000)
        self._update_contextual_knob_configs()

    def _some_method_that_triggers_animator_stop(self):
        if self.animator_manager:
            # Set the flag BEFORE telling the animator to stop,
            # so _on_animator_playback_status_for_oled (called when playback status changes to False)
            # knows it was an explicit stop.
            self._stop_action_issued_for_oled = True
            self.animator_manager.action_stop()
            # The _on_animator_playback_status_for_oled slot will then correctly show "■ STOP"

    def _handle_hardware_animator_stop_request(self):
        if self.animator_manager:
            self._stop_action_issued_for_oled = True
            self.animator_manager.action_stop()

    def clear_all_hardware_and_gui_pads(self):
        """
        Clears all hardware pads to black and also clears the current
        GUI pad grid representation (e.g., current animator frame).
        Stops active sampler or animator playback.
        """
        if not self.akai_controller or not self.akai_controller.is_connected():
            self.status_bar.showMessage("Connect to Akai Fire first to clear pads.", 2500)
            return        
        # Stop any ongoing processes that might interfere or immediately repaint
        if self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active():
            self.screen_sampler_manager.stop_sampling_thread()
            self.status_bar.showMessage("Sampler stopped by Clear Pads action.", 2000)        
        if self.animator_manager and self.animator_manager.active_sequence_model and \
            self.animator_manager.active_sequence_model.get_is_playing():
            self.animator_manager.action_stop() # Stop animator playback
            self.status_bar.showMessage("Animation stopped by Clear Pads action.", 2000)
        self.clear_main_pad_grid_ui(update_hw=True, is_sampler_output=False) 
        if self.animator_manager and self.animator_manager.active_sequence_model:
            self.animator_manager.active_sequence_model.clear_pads_in_current_edit_frame()
        self.status_bar.showMessage("All pads and current GUI view cleared to black.", 2500)

    def _handle_request_sampler_disable(self):
        if self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active():
            self.screen_sampler_manager.stop_sampling_thread() 
            # self.status_bar.showMessage("Sampler deactivated by other component.", 2000) # Optional

    def _on_oled_startup_animation_finished(self):
        # print("MW TRACE: _on_oled_startup_animation_finished called.") # Optional
        if not self.oled_display_manager:
            print("MW WARNING: OLEDDisplayManager not available in _on_oled_startup_animation_finished.") # Optional
            return
        # The logic inside this method should now be minimal as ODM handles the transition.
        print("MW INFO: Built-in OLED startup animation finished. OLED Manager is handling transition to Active Graphic.") # Optional
        pass

    def _on_sampler_activity_changed(self, is_active: bool):
        """
        Handles sampler start/stop to show temporary OLED cues and update UI/animator state.
        The Active Graphic will resume after the temporary cue.
        """
        # print(f"MW TRACE: _on_sampler_activity_changed - Sampler Active: {is_active}") # Optional
        if self.oled_display_manager:
            if is_active:  # Sampler just started
                monitor_name_part = "Mon: ?"  # Default
                if self.screen_sampler_manager and self.screen_sampler_manager.screen_sampler_monitor_list_cache:
                    current_mon_id = self.screen_sampler_manager.current_sampler_params.get(
                        'monitor_id', 1)
                    mon_info = next(
                        (m for m in self.screen_sampler_manager.screen_sampler_monitor_list_cache if m['id'] == current_mon_id), None)
                    if mon_info:
                        name_part = mon_info.get(
                            'name_for_ui', f"ID {current_mon_id}")
                        # Attempt to shorten "Monitor X (WxH)" to just "Monitor X" or "X"
                        match = re.match(r"(Monitor\s*\d+)", name_part)
                        if match:
                            name_part = match.group(1)
                        elif "Monitor" in name_part and "(" in name_part:
                            try:
                                name_part = name_part.split("(")[0].strip()
                            except:
                                pass
                        monitor_name_part = f"Mon: {name_part}"
                message_text = f"Sampler ON ({monitor_name_part})"
                self.oled_display_manager.show_system_message(
                    text=message_text,
                    duration_ms=2000,  # Show for 2 seconds
                    scroll_if_needed=True
                )
            else:  # Sampler just stopped
                self.oled_display_manager.show_system_message(
                    text="Sampler OFF",
                    duration_ms=2000,  # Show for 2 seconds
                    scroll_if_needed=True
                )
        # Stop animator if sampler starts
        if is_active and self.animator_manager:
            self.animator_manager.action_stop()
        # Restore animator's current frame to the grid if sampler just stopped AND animator is not playing
        elif not is_active:
            if self.animator_manager and self.animator_manager.active_sequence_model and \
                not self.animator_manager.active_sequence_model.get_is_playing():
                edit_idx = self.animator_manager.active_sequence_model.get_current_edit_frame_index()
                colors = self.animator_manager.active_sequence_model.get_frame_colors(
                    edit_idx)
                self._on_animator_frame_data_for_display(colors)
            elif not self.animator_manager or not self.animator_manager.active_sequence_model:
                # If no animator sequence active, ensure grid is cleared or shows static default
                self._on_animator_frame_data_for_display(None)
        self._update_global_ui_interaction_states()
        self._update_contextual_knob_configs()

    def _toggle_oled_active_graphic_pause(self):
        # print("MW DEBUG: _toggle_oled_active_graphic_pause called") 
        if not self.oled_display_manager:
            # print("MW DEBUG: OLEDDisplayManager is None in _toggle_oled_active_graphic_pause.")
            return
        
        if self.oled_display_manager.is_active_graphic_paused():
            self.oled_display_manager.resume_active_graphic()
            self.oled_manual_override_active_state = False # User manually set to PLAY
            # print("MW DEBUG: Manually requested RESUME OLED, override state = False (User wants Play)")
        else:
            self.oled_display_manager.pause_active_graphic()
            self.oled_manual_override_active_state = True # User manually set to PAUSE
            # print("MW DEBUG: Manually requested PAUSE OLED, override state = True (User wants Pause)")

    def _handle_final_color_selection_from_manager(self, color: QColor):
        """
        Handles the final_color_selected signal from the ColorPickerManager.
        Updates the main window's currently active painting color.
        """
        if isinstance(color, QColor) and color.isValid():
            self.selected_qcolor = color
            # print(f"MW DEBUG: Final color selected from manager: {color.name()}") # Optional debug
            if self.status_bar: # Check if status_bar exists
                self.status_bar.showMessage(f"Active painting color set to: {color.name().upper()}", 3000)
        # else: # Optional
            # print(f"MW WARNING: Invalid color received from ColorPickerManager: {color}")
            # if self.status_bar:
            #     self.status_bar.showMessage(f"Invalid color selected.", 2000)

    def _on_animator_playback_status_changed_for_knobs(self, is_playing: bool):
        self.is_animator_playing = is_playing
        if is_playing:
            self.status_bar.showMessage("Knob 4 now controls Animation Speed (FPS).", 4000)
        self._update_contextual_knob_configs()

    def _update_oled_mirror(self, packed_bitmap_data_7bit: bytearray):
        """Updates the on-screen OLED mirror widget."""
        # print(
            # f"MW DEBUG: _update_oled_mirror CALLED. Data length: {len(packed_bitmap_data_7bit) if packed_bitmap_data_7bit else 'None'}")
        # if not self.oled_display_mirror_widget:
            # print("MW DEBUG: _update_oled_mirror - Mirror widget is None, returning.")
            # return
        if not (MAIN_WINDOW_OLED_RENDERER_AVAILABLE and hasattr(oled_renderer, '_unpack_fire_7bit_stream_to_logical_image')):
            # print("MW DEBUG: _update_oled_mirror - Renderer or unpack function not available.")
            blank_pixmap = QPixmap(self.oled_display_mirror_widget.size())
            blank_pixmap.fill(Qt.GlobalColor.darkGray)
            painter = QPainter(blank_pixmap)
            painter.setPen(Qt.GlobalColor.white)
            font = painter.font()
            font.setPointSize(
                max(6, int(self.oled_display_mirror_widget.height() / 8)))
            painter.setFont(font)
            painter.drawText(blank_pixmap.rect(),
                            Qt.AlignmentFlag.AlignCenter, "Renderer N/A")
            painter.end()
            self.oled_display_mirror_widget.setPixmap(blank_pixmap)
            return
        try:
            # print("MW DEBUG: _update_oled_mirror - Attempting to unpack stream...")
            pil_image_logical = oled_renderer._unpack_fire_7bit_stream_to_logical_image(
                packed_bitmap_data_7bit, OLED_MIRROR_WIDTH, OLED_MIRROR_HEIGHT
            )
            if pil_image_logical:
                pil_image_rgb = pil_image_logical.convert("RGB")
                data = pil_image_rgb.tobytes("raw", "RGB")
                qimage = QImage(data, pil_image_rgb.width,
                                pil_image_rgb.height, QImage.Format.Format_RGB888)
                if not qimage.isNull():
                    #  print("MW DEBUG: _update_oled_mirror - QImage conversion successful.")
                    q_pixmap = QPixmap.fromImage(qimage)
                    scaled_pixmap = q_pixmap.scaled(
                        self.oled_display_mirror_widget.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.FastTransformation
                    )
                    self.oled_display_mirror_widget.setPixmap(scaled_pixmap)
                    # print("MW DEBUG: _update_oled_mirror - Pixmap set on mirror.") # Can be very noisy
                else:
                    # print(
                    #    "MW WARNING: _update_oled_mirror - QImage isNull after conversion.")
                    blank_pixmap = QPixmap(
                        self.oled_display_mirror_widget.size())
                    blank_pixmap.fill(Qt.GlobalColor.black)
                    self.oled_display_mirror_widget.setPixmap(blank_pixmap)
            else:
                # print(
                #     "MW WARNING: _update_oled_mirror - _unpack_fire_7bit_stream_to_logical_image returned None.")
                blank_pixmap = QPixmap(self.oled_display_mirror_widget.size())
                blank_pixmap.fill(Qt.GlobalColor.darkBlue)
                self.oled_display_mirror_widget.setPixmap(blank_pixmap)
        except Exception as e:
            # print(f"MW ERROR: Exception in _update_oled_mirror: {e}")
            import traceback
            traceback.print_exc()  
            error_pixmap = QPixmap(self.oled_display_mirror_widget.size())
            error_pixmap.fill(Qt.GlobalColor.darkRed)
            # Ensure QPainter is imported in MainWindow
            painter = QPainter(error_pixmap)
            painter.setPen(Qt.GlobalColor.white)
            font = painter.font()
            font.setPointSize(
                max(6, int(self.oled_display_mirror_widget.height() / 7)))
            painter.setFont(font)
            painter.drawText(error_pixmap.rect(),
                            Qt.AlignmentFlag.AlignCenter, "Mirror Err")
            painter.end()
            self.oled_display_mirror_widget.setPixmap(error_pixmap)

    def _open_app_guide_dialog(self):
        """
        Creates and shows the AppGuideDialog.
        """
        guide_dialog = AppGuideDialog(self)  # Pass self as parent
        guide_dialog.exec()  # Show as a modal dialog
        guide_dialog.deleteLater()

    def _on_animator_undo_redo_state_changed(self, can_undo: bool, can_redo: bool):
        if self.undo_action: self.undo_action.setEnabled(can_undo)
        if self.redo_action: self.redo_action.setEnabled(can_redo)
        self._update_global_ui_interaction_states() # Might affect other dependent actions

    def _update_fire_transport_leds(self, is_animator_playing: bool):
        """
        This method is called when animator playback state changes.
        Play/Stop LED control is now overridden in AkaiFireController to keep them OFF.
        This method can be left empty or log, as direct calls to set_play_led/set_stop_led
        will be forced to OFF by AkaiFireController.
        """
        # print(f"DEBUG MW: _update_fire_transport_leds - Animator playing: {is_animator_playing}. (Play/Stop LEDs are forced OFF by AkaiFireController)") # Optional        
        pass

    def action_animator_undo(self):
        if self.animator_manager: self.animator_manager.action_undo()

    def action_animator_redo(self):
        if self.animator_manager: self.animator_manager.action_redo()

    def action_animator_copy_frames(self):
        if self.animator_manager: self.animator_manager.action_copy_frames()

    def action_animator_cut_frames(self):
        if self.animator_manager: self.animator_manager.action_cut_frames()

    def action_animator_paste_frames(self):
        if self.animator_manager: self.animator_manager.action_paste_frames()

    def action_animator_duplicate_frames(self):
        if self.animator_manager: self.animator_manager.action_duplicate_selected_frames()

    def action_animator_delete_frames(self):
        if self.animator_manager: self.animator_manager.action_delete_selected_frames()

    def action_animator_add_blank_frame(self): # For global QAction
        if self.animator_manager: self.animator_manager.action_add_frame("blank") # Default add

    def action_animator_new_sequence(self, prompt_save=True): # For global QAction
        if self.animator_manager:
            # Handle "save current modified" prompt here in MainWindow
            if prompt_save and self.animator_manager.active_sequence_model and \
                self.animator_manager.active_sequence_model.is_modified:
                reply = QMessageBox.question(self, "Unsaved Changes",
                                            f"Animation '{self.animator_manager.active_sequence_model.name}' has unsaved changes. Save now?",
                                            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                            QMessageBox.StandardButton.Cancel)
                if reply == QMessageBox.StandardButton.Save:
                    save_successful = self.animator_manager.action_save_sequence_as() # AMW handles dialog
                    if not save_successful: # User might cancel Save As dialog
                        self.status_bar.showMessage("New sequence creation cancelled.", 2000)
                        return # Don't proceed if save failed or was cancelled
                elif reply == QMessageBox.StandardButton.Cancel:
                    self.status_bar.showMessage("New sequence creation cancelled.", 2000)
                    return           
            # If Discard or if not modified, or if save was successful, proceed
            self.animator_manager.action_new_sequence(prompt_save=False) # Tell AMW not to prompt again

    def action_animator_save_sequence_as(self): # For global QAction
        if self.animator_manager: self.animator_manager.action_save_sequence_as()

    def action_animator_play_pause_toggle(self):
        if self.animator_manager:
            self.animator_manager.action_play_pause_toggle() 
            if self.animator_manager.active_sequence_model:
                self._update_fire_transport_leds(self.animator_manager.active_sequence_model.get_is_playing())
            else:
                self._update_fire_transport_leds(False)

    def _handle_animator_request_load_prompt(self, filepath_to_load: str):
        """Handles AnimatorManager's request to load, prompting for save if needed."""
        if not self.animator_manager: return
        proceed_with_load = True 
        if self.animator_manager.active_sequence_model and \
            self.animator_manager.active_sequence_model.is_modified:
            reply = QMessageBox.question(self, "Unsaved Animator Changes",
                                        f"Animation '{self.animator_manager.active_sequence_model.name}' has unsaved changes.\nSave before loading new sequence?",
                                        QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                        QMessageBox.StandardButton.Cancel) 
            if reply == QMessageBox.StandardButton.Save:
                if not self.animator_manager.action_save_sequence_as(): proceed_with_load = False
            elif reply == QMessageBox.StandardButton.Cancel: proceed_with_load = False 
            elif reply == QMessageBox.StandardButton.Discard: self.status_bar.showMessage("Changes discarded.",1500)
            else: proceed_with_load = False       
        if proceed_with_load:
            self.animator_manager._handle_load_sequence_request(filepath_to_load) # Tell AMW to do the actual load

    def _handle_load_sequence_request(self, filepath_to_load: str):
        """Handles loading a sequence (e.g., from sampler recording), prompting if needed."""
        # This is similar to _handle_animator_request_load_prompt but might have different context/messages.
        if not self.animator_manager: return
        proceed_with_load = True
        if self.animator_manager.active_sequence_model and \
            self.animator_manager.active_sequence_model.is_modified:
            reply = QMessageBox.question(self, "Unsaved Animator Changes",
                                        f"Current animation has unsaved changes. Save before loading '{os.path.basename(filepath_to_load)}'?",
                                        QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                        QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                if not self.animator_manager.action_save_sequence_as(): proceed_with_load = False
            elif reply == QMessageBox.StandardButton.Cancel: proceed_with_load = False        
        if proceed_with_load:
            self.animator_manager._handle_load_sequence_request(filepath_to_load)
            self.status_bar.showMessage(f"Sequence '{os.path.basename(filepath_to_load)}' loaded.", 2500)

    def toggle_eyedropper_mode(self, checked: bool | None = None): # From QAction
        new_state = not self.is_eyedropper_mode_active if checked is None else checked
        self.set_eyedropper_mode(new_state)

    def set_eyedropper_mode(self, active: bool):
        if self.is_eyedropper_mode_active == active:
            # If the ColorPickerManager button exists, ensure its state is correct even if mode didn't change overall
            if self.color_picker_manager and self.color_picker_manager.eyedropper_button:
                if self.color_picker_manager.eyedropper_button.isChecked() != active:
                    self.color_picker_manager.eyedropper_button.setChecked(active)
            return
        self.is_eyedropper_mode_active = active
        cursor_shape = Qt.CursorShape.CrossCursor if active else Qt.CursorShape.ArrowCursor
        if self.pad_grid_frame:
            self.pad_grid_frame.setCursor(cursor_shape)
        
        status_msg = "Eyedropper active: Click a pad to pick its color." if active else "Eyedropper deactivated."
        self.status_bar.showMessage(status_msg, 0 if active else 2000) # Keep message visible while active
        # Sync the ColorPickerManager's eyedropper button
        if self.color_picker_manager and self.color_picker_manager.eyedropper_button:
            # Block its signals temporarily while setting state to avoid re-emitting toggled
            self.color_picker_manager.eyedropper_button.blockSignals(True)
            if self.color_picker_manager.eyedropper_button.isChecked() != active:
                self.color_picker_manager.eyedropper_button.setChecked(active)
            self.color_picker_manager.eyedropper_button.blockSignals(False)
        # Sync the global QAction for eyedropper
        if hasattr(self, 'eyedropper_action') and self.eyedropper_action:
            if self.eyedropper_action.isChecked() != active:
                self.eyedropper_action.setChecked(active)
        self._update_global_ui_interaction_states() # Update global UI states

    def _pick_color_from_pad(self, row: int, col: int):
        if not self.color_picker_manager or not self.pad_grid_frame: return
        # Assuming pad_grid_frame stores colors in a way that can be retrieved by row/col
        # For now, let's assume _get_current_main_pad_grid_colors returns a flat list
        all_grid_colors = self.pad_grid_frame.get_current_grid_colors_hex() 
        pad_1d_index = row * 16 + col 
        if 0 <= pad_1d_index < len(all_grid_colors):
            hex_color_str = all_grid_colors[pad_1d_index]
            picked_qcolor = QColor(hex_color_str)
            if picked_qcolor.isValid():
                self.color_picker_manager.set_current_selected_color(picked_qcolor, source="eyedropper")
                self.status_bar.showMessage(f"Color picked: {picked_qcolor.name().upper()}", 3000)
                self.set_eyedropper_mode(False) # Deactivate after pick
            else: self.status_bar.showMessage("Eyedropper: Invalid pad color.", 2000)
        else: self.status_bar.showMessage("Eyedropper: Invalid pad index.", 2000)

    def _handle_grid_pad_action(self, row: int, col: int, mouse_button: Qt.MouseButton):
        if mouse_button == Qt.MouseButton.LeftButton and self.is_eyedropper_mode_active:
            self._pick_color_from_pad(row, col); return 
        if self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active():
            self.screen_sampler_manager.stop_sampling_thread()
            self.status_bar.showMessage("Sampler stopped by pad interaction.", 2000)
        if self.animator_manager and self.animator_manager.active_sequence_model and \
            self.animator_manager.active_sequence_model.get_is_playing():
            self.animator_manager.action_stop()
            self.status_bar.showMessage("Animation stopped by pad interaction.", 2000)
        if mouse_button == Qt.MouseButton.LeftButton:
            self.apply_paint_to_pad(row, col, update_model=True)
        elif mouse_button == Qt.MouseButton.RightButton:
            self.apply_erase_to_pad(row, col, update_model=True)

    def apply_colors_to_main_pad_grid(self, colors_hex: list | None, update_hw: bool = True, is_sampler_output: bool = False):
        """
        Applies a list of 64 hex color strings to the main GUI pad grid.
        Optionally updates the hardware pads as well.
        'is_sampler_output' flag is used by AkaiFireController to potentially bypass global brightness.
        """
        if not hasattr(self, 'pad_grid_frame') or not self.pad_grid_frame:
            # print("MW WARNING: apply_colors_to_main_pad_grid - pad_grid_frame is None.") # Optional
            return
        if not colors_hex or not isinstance(colors_hex, list) or len(colors_hex) != 64:
            # print(f"MW DEBUG: apply_colors_to_main_pad_grid called with invalid colors_hex, clearing grid. update_hw={update_hw}, is_sampler_output={is_sampler_output}") # Optional
            self.clear_main_pad_grid_ui(update_hw=update_hw, is_sampler_output=is_sampler_output)
            return           
        hw_batch = []
        for i, hex_str in enumerate(colors_hex):
            r, c = divmod(i, 16) # Convert 1D index to 2D row/col          
            # Ensure hex_str is valid, default to black if not
            current_color = QColor(hex_str if (hex_str and isinstance(hex_str, str)) else "#000000")
            if not current_color.isValid():
                current_color = QColor("black") # Fallback to black for invalid hex           
            # Update GUI pad color
            self.pad_grid_frame.update_pad_gui_color(r, c, current_color.red(), current_color.green(), current_color.blue())            
            # Prepare batch for hardware update
            if update_hw:
                hw_batch.append((r, c, current_color.red(), current_color.green(), current_color.blue()))       
        # Update hardware pads if requested and controller is connected
        if update_hw and self.akai_controller and self.akai_controller.is_connected() and hw_batch:
            # The 'is_sampler_output' flag tells the controller whether to apply global brightness
            # (bypass_global_brightness = is_sampler_output)
            self.akai_controller.set_multiple_pads_color(hw_batch, bypass_global_brightness=is_sampler_output)
            # print(f"MW DEBUG: Sent {len(hw_batch)} pad colors to hardware. is_sampler_output={is_sampler_output}") # Optional

    def clear_main_pad_grid_ui(self, update_hw=True, is_sampler_output: bool = False):
        if not hasattr(self, 'pad_grid_frame') or not self.pad_grid_frame:
            # print("MW WARNING: clear_main_pad_grid_ui - pad_grid_frame is None.") # Optional
            return
        self.apply_colors_to_main_pad_grid(
            [QColor("black").name()] * 64, 
            update_hw=update_hw,
            is_sampler_output=is_sampler_output # Propagate flag
        )

    def _handle_grid_pad_single_left_click(self, row: int, col: int): # Primarily for eyedropper
        if self.is_eyedropper_mode_active: self._pick_color_from_pad(row, col)

    def apply_paint_to_pad(self, row: int, col: int, update_model: bool = True):
        if not self.akai_controller.is_connected(): return
        r, g, b, _ = self.selected_qcolor.getRgb()
        self.akai_controller.set_pad_color(row, col, r, g, b)
        if self.pad_grid_frame: self.pad_grid_frame.update_pad_gui_color(row, col, r, g, b)
        if update_model and self.animator_manager and self.animator_manager.active_sequence_model:
            self.animator_manager.active_sequence_model.update_pad_in_current_edit_frame(
                row * 16 + col, self.selected_qcolor.name()
            )

    def apply_erase_to_pad(self, row: int, col: int, update_model: bool = True):
        if not self.akai_controller.is_connected(): return
        self.akai_controller.set_pad_color(row, col, 0, 0, 0)
        if self.pad_grid_frame: self.pad_grid_frame.update_pad_gui_color(row, col, 0, 0, 0)
        if update_model and self.animator_manager and self.animator_manager.active_sequence_model: 
            self.animator_manager.active_sequence_model.update_pad_in_current_edit_frame(
                row * 16 + col, QColor("black").name()
            )

    def show_pad_context_menu(self, pad_button_widget: QPushButton, row: int, col: int, local_pos_to_button: QPoint):
        menu = QMenu(self)
        action_set_off = QAction("Set Pad to Black (Off)", self)
        action_set_off.triggered.connect(lambda: self.set_single_pad_black_and_update_model(row, col))
        menu.addAction(action_set_off)
        menu.exec(pad_button_widget.mapToGlobal(local_pos_to_button))

    def set_single_pad_black_and_update_model(self, row: int, col: int):
        if self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active():
            self.screen_sampler_manager.stop_sampling_thread()
        self.apply_erase_to_pad(row, col, update_model=True)
        self.status_bar.showMessage(f"Pad ({row+1},{col+1}) set to Off.", 1500)

    def _on_animator_frame_data_for_display(self, colors_hex_list: list | None):
        if colors_hex_list and isinstance(colors_hex_list, list) and len(colors_hex_list) == 64:
            self.apply_colors_to_main_pad_grid(colors_hex_list, update_hw=True)
        else: 
            self.clear_main_pad_grid_ui(update_hw=True)

    def _on_animator_clipboard_state_changed(self, has_content: bool):
        if self.paste_action: self.paste_action.setEnabled(has_content)
        self._update_global_ui_interaction_states()

    def _on_animator_undo_redo_state_changed(self, can_undo: bool, can_redo: bool):
        """
        Updates the enabled state of global Undo and Redo QActions.
        This is connected to AnimatorManagerWidget.undo_redo_state_changed.
        """
        if self.undo_action: # Check if QAction exists
            self.undo_action.setEnabled(can_undo)
        if self.redo_action: # Check if QAction exists
            self.redo_action.setEnabled(can_redo)
        self._update_global_ui_interaction_states()

    def _on_global_brightness_slider_changed(self, value: int):
        # Update the label next to the slider
        if hasattr(self, 'brightness_value_label'):
            self.brightness_value_label.setText(f"{value}%")
        # Call the existing logic handler
        self._on_global_brightness_knob_changed(value)

    def _on_global_brightness_knob_changed(self, value: int):
        self.global_pad_brightness = value / 100.0
        # Sync the new GUI slider if its value is different
        if hasattr(self, 'global_brightness_slider') and self.global_brightness_slider.value() != value:
            self.global_brightness_slider.blockSignals(True)
            self.global_brightness_slider.setValue(value)
            self.global_brightness_slider.blockSignals(False)
            if hasattr(self, 'brightness_value_label'):
                self.brightness_value_label.setText(f"{value}%")

        # Sync the visual knob indicator
        visual_knob = getattr(self, "knob_volume_top_right_visual", None)
        if visual_knob:
            angle = -135 + (value / 100.0) * 270.0
            visual_knob.set_indicator_angle(angle)

        # Apply the change to the hardware
        if self.akai_controller:
            self.akai_controller.set_global_brightness_factor(self.global_pad_brightness)
            
        is_sampler_active = self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active()
        is_anim_playing = self.is_animator_playing
        
        if not is_sampler_active and not is_anim_playing and self.pad_grid_frame:
            current_colors_hex = self.pad_grid_frame.get_current_grid_colors_hex()
            self.apply_colors_to_main_pad_grid(current_colors_hex, update_hw=True, is_sampler_output=False)

    def _on_sampler_brightness_knob_changed(self, gui_knob_value: int):
        if self.screen_sampler_manager:
            sampler_factor = gui_knob_value / 100.0
            sampler_factor = max(0.0, sampler_factor)
            self.screen_sampler_manager.update_sampler_adjustment('brightness', sampler_factor)

    def _on_sampler_saturation_knob_changed(self, gui_knob_value: int):
        if self.screen_sampler_manager:
            sampler_factor = gui_knob_value / 100.0
            sampler_factor = max(0.0, sampler_factor)
            self.screen_sampler_manager.update_sampler_adjustment('saturation', sampler_factor)

    def _on_sampler_contrast_knob_changed(self, gui_knob_value: int):
        if self.screen_sampler_manager:
            sampler_factor = gui_knob_value / 100.0
            sampler_factor = max(0.0, sampler_factor)
            self.screen_sampler_manager.update_sampler_adjustment('contrast', sampler_factor)

    def _on_sampler_hue_knob_changed(self, gui_knob_value: int):
        if self.screen_sampler_manager:
            self.screen_sampler_manager.update_sampler_adjustment('hue_shift', float(gui_knob_value))


    def _handle_knob1_change(self, value: int):
        sampler_is_active = self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active()
        qdial = self.knob_volume_top_right
        visual_knob = getattr(self, "knob_volume_top_right_visual", None)
        knob_stack = getattr(self, "knob_volume_top_right_stack", None)
        if visual_knob and qdial:
            min_val, max_val = qdial.minimum(), qdial.maximum()
            if max_val > min_val:
                angle = -135 + ((value - min_val) /
                                (max_val - min_val)) * 270.0
                visual_knob.set_indicator_angle(angle)
        if sampler_is_active:
            self._on_sampler_brightness_knob_changed(value)
            if knob_stack:
                knob_stack.setToolTip(
                    f"Sampler: Brightness ({value / 100.0:.2f}x)")
            self._show_knob_feedback_on_oled(f"Br: {value / 100.0:.2f}x")
        else:
            self._on_global_brightness_knob_changed(value)
            if knob_stack:
                knob_stack.setToolTip(f"Global Pad Brightness ({value}%)")
            self._show_knob_feedback_on_oled(f"GlbBr: {value}%")

    def _handle_knob2_change(self, value: int):
        qdial = self.knob_pan_top_right
        visual_knob = getattr(self, "knob_pan_top_right_visual", None)
        knob_stack = getattr(self, "knob_pan_top_right_stack", None)
        if visual_knob and qdial:
            min_val, max_val = qdial.minimum(), qdial.maximum()
            if max_val > min_val:
                angle = -135 + ((value - min_val) /
                                (max_val - min_val)) * 270.0
                visual_knob.set_indicator_angle(angle)
        if self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active():
            self._on_sampler_saturation_knob_changed(value)
            if knob_stack:
                knob_stack.setToolTip(
                    f"Sampler: Saturation ({value / 100.0:.2f}x)")
            self._show_knob_feedback_on_oled(f"Sat: {value / 100.0:.2f}x")

    def _handle_knob3_change(self, value: int):
        qdial = self.knob_filter_top_right
        visual_knob = getattr(self, "knob_filter_top_right_visual", None)
        knob_stack = getattr(self, "knob_filter_top_right_stack", None)

        if visual_knob and qdial:
            min_val, max_val = qdial.minimum(), qdial.maximum()
            if max_val > min_val:
                angle = -135 + ((value - min_val) /
                                (max_val - min_val)) * 270.0
                visual_knob.set_indicator_angle(angle)

        if self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active():
            self._on_sampler_contrast_knob_changed(value)
            if knob_stack:
                knob_stack.setToolTip(
                    f"Sampler: Contrast ({value / 100.0:.2f}x)")
            self._show_knob_feedback_on_oled(f"Con: {value / 100.0:.2f}x")

    def _handle_knob4_change(self, value: int):
        sampler_is_active = self.screen_sampler_manager and self.screen_sampler_manager.is_sampling_active()
        qdial = self.knob_resonance_top_right
        visual_knob = getattr(self, "knob_resonance_top_right_visual", None)
        knob_stack = getattr(self, "knob_resonance_top_right_stack", None)
        if visual_knob and qdial:
            min_val, max_val = qdial.minimum(), qdial.maximum()
            if max_val > min_val:
                angle = -135 + ((value - min_val) /
                                (max_val - min_val)) * 270.0
                visual_knob.set_indicator_angle(angle)
        if self.is_animator_playing:
            self._on_animator_speed_knob_changed(value)
        elif sampler_is_active:
            self._on_sampler_hue_knob_changed(value)

    def _cycle_oled_nav_target(self, direction: int):
        """Cycles the OLED navigation focus and shows a temporary cue."""
        if self._oled_nav_debounce_timer.isActive():
            return
        self._oled_nav_debounce_timer.start()
        current_focus_idx = self.OLED_NAVIGATION_FOCUS_OPTIONS.index(
            self.current_oled_nav_target_name)
        new_focus_idx = (current_focus_idx + direction + len(
            self.OLED_NAVIGATION_FOCUS_OPTIONS)) % len(self.OLED_NAVIGATION_FOCUS_OPTIONS)
        self.current_oled_nav_target_name = self.OLED_NAVIGATION_FOCUS_OPTIONS[new_focus_idx]
        self._update_current_oled_nav_target_widget()
        nav_target_display_name = "Unknown Panel"
        if self.current_oled_nav_target_name == "animator":
            nav_target_display_name = "Animator Focus"  # Or just "Animator"
        elif self.current_oled_nav_target_name == "static_layouts":
            nav_target_display_name = "Layouts Focus"  # Or just "Static Layouts"
        if self.oled_display_manager:
            self.oled_display_manager.show_system_message(
                text=nav_target_display_name,
                duration_ms=1500,
                scroll_if_needed=True
            )
        self._oled_nav_interaction_active = False

    def _handle_select_encoder_turned(self, delta: int):
        """Handles SELECT knob rotation for item navigation, shows temporary item name cue."""
        if not self.current_oled_nav_target_widget or \
            not (self.akai_controller and self.akai_controller.is_connected()) or \
            not hasattr(self.current_oled_nav_target_widget, 'set_navigation_current_item_by_logical_index') or \
            not hasattr(self.current_oled_nav_target_widget, 'get_navigation_item_text_at_logical_index'):
            return
        if self._oled_nav_item_count == 0:
            nav_target_display_name = "Animator" if self.current_oled_nav_target_name == "animator" else "Layouts"
            if self.oled_display_manager:
                self.oled_display_manager.show_system_message(
                    f"{nav_target_display_name}: (empty)", 1500, scroll_if_needed=False)
            return
        self._oled_nav_interaction_active = True
        new_logical_index = (
            self.current_oled_nav_item_logical_index + delta) % self._oled_nav_item_count
        if new_logical_index < 0:
            new_logical_index += self._oled_nav_item_count
        self.current_oled_nav_item_logical_index = new_logical_index
        selected_item_text_with_prefix = "Error"
        try:
            selected_item_text_with_prefix = self.current_oled_nav_target_widget.set_navigation_current_item_by_logical_index(
                self.current_oled_nav_item_logical_index
            ) or "N/A"
        except Exception as e:
            print(
                f"MW ERROR: Navigating item in {self.current_oled_nav_target_name}: {e}")
        if self.oled_display_manager:
            clean_item_text = selected_item_text_with_prefix
            for prefix in ["[Prefab] ", "[Sampler] ", "[User] "]:
                if clean_item_text.startswith(prefix):
                    clean_item_text = clean_item_text[len(prefix):]
                    break
            self.oled_display_manager.show_system_message(
                text=clean_item_text,
                duration_ms=1000,  # Short duration, updates frequently with knob turns
                scroll_if_needed=True
            )

    def _handle_select_encoder_pressed(self):
        """Handles SELECT knob press to apply/load item, shows temporary confirmation cue."""
        if not self.current_oled_nav_target_widget or \
            not (self.akai_controller and self.akai_controller.is_connected()) or \
            not hasattr(self.current_oled_nav_target_widget, 'trigger_navigation_current_item_action') or \
            not hasattr(self.current_oled_nav_target_widget, 'get_navigation_item_text_at_logical_index'):
            return
        if self._oled_nav_item_count == 0:
            if self.oled_display_manager:
                self.oled_display_manager.show_system_message(
                    "(No item)", 1500, scroll_if_needed=False)
            return
        self._is_hardware_nav_action_in_progress = True
        item_text_to_apply_raw = "Selected Item"
        try:
            item_text_to_apply_raw = self.current_oled_nav_target_widget.get_navigation_item_text_at_logical_index(
                self.current_oled_nav_item_logical_index
            ) or "Selected Item"
        except Exception as e:
            print(
                f"MW ERROR: Getting item text for select press in {self.current_oled_nav_target_name}: {e}")
        item_text_to_apply_clean = item_text_to_apply_raw
        for prefix in ["[Prefab] ", "[Sampler] ", "[User] "]:
            if item_text_to_apply_clean.startswith(prefix):
                item_text_to_apply_clean = item_text_to_apply_clean[len(
                    prefix):]
                break
        action_verb = "Loading" if self.current_oled_nav_target_name == "animator" else "Applying"
        if self.oled_display_manager:
            confirm_item_name_part = item_text_to_apply_clean[:15] + "..." if len(
                item_text_to_apply_clean) > 15 else item_text_to_apply_clean
            full_confirmation_message = f"{action_verb}: {confirm_item_name_part}"
            self.oled_display_manager.show_system_message(
                text=full_confirmation_message,
                duration_ms=1800,
                scroll_if_needed=True
            )
        try:
            self.current_oled_nav_target_widget.trigger_navigation_current_item_action()
        except Exception as e:
            print(
                f"MW ERROR: Triggering navigation action in {self.current_oled_nav_target_name}: {e}")
            if self.oled_display_manager:
                self.oled_display_manager.show_system_message(
                    "Action Error", 1500, scroll_if_needed=False)
        self._oled_nav_interaction_active = False
        QTimer.singleShot(2000, self._finalize_navigation_action_ui_feedback)  # _finalize will ensure Active Graphic resumes

    def _handle_grid_left_pressed(self):
        self._cycle_oled_nav_target(1)

    def _handle_oled_pattern_up(self):
        """Handles PATTERN UP for cueing next OLED item, shows temporary cue."""
        if not self.oled_display_manager or not (self.akai_controller and self.akai_controller.is_connected()): return
        if not self.available_oled_items_cache:
            self.oled_display_manager.show_system_message("No Items", 1500, scroll_if_needed=False)
            return
        current_idx = -1
        # Ensure self.current_cued_item_path is initialized in __init__ if not already
        if not hasattr(self, 'current_cued_item_path'): self.current_cued_item_path = None
        if self.current_cued_item_path:
            try:
                current_idx = [item['path'] for item in self.available_oled_items_cache].index(self.current_cued_item_path)
            except ValueError: current_idx = -1 
        new_idx = (current_idx + 1) % len(self.available_oled_items_cache)
        cued_item = self.available_oled_items_cache[new_idx]
        self.current_cued_item_path = cued_item['path'] 
        item_name_to_show = cued_item['name']
        item_type_label = cued_item['type'][:1].upper() # "T" or "A"
        
        self.oled_display_manager.show_system_message(
            text=f"Cue ({item_type_label}): {item_name_to_show}",
            duration_ms=2000, 
            scroll_if_needed=True
        )
        self._save_oled_config() # Save the new cued item path

    def _handle_oled_pattern_down(self):
        """Handles PATTERN DOWN for cueing previous OLED item, shows temporary cue."""
        if not self.oled_display_manager or not (self.akai_controller and self.akai_controller.is_connected()): return
        
        if not self.available_oled_items_cache:
            self.oled_display_manager.show_system_message("No Items", 1500, scroll_if_needed=False)
            return
        current_idx = 0 
        if not hasattr(self, 'current_cued_item_path'): self.current_cued_item_path = None
        if self.current_cued_item_path:
            try:
                current_idx = [item['path'] for item in self.available_oled_items_cache].index(self.current_cued_item_path)
            except ValueError: current_idx = 0 
        new_idx = (current_idx - 1 + len(self.available_oled_items_cache)) % len(self.available_oled_items_cache)
        cued_item = self.available_oled_items_cache[new_idx]
        self.current_cued_item_path = cued_item['path']
        item_name_to_show = cued_item['name']
        item_type_label = cued_item['type'][:1].upper()
        self.oled_display_manager.show_system_message(
            text=f"Cue ({item_type_label}): {item_name_to_show}",
            duration_ms=2000,
            scroll_if_needed=True
        )
        self._save_oled_config()

    def _handle_oled_browser_activate(self):
        """Handles BROWSER button to set cued item as Active Graphic, shows temp confirmation."""
        if not self.oled_display_manager or not (self.akai_controller and self.akai_controller.is_connected()): return
        item_path_to_activate = getattr(self, 'current_cued_item_path', None)
        
        if not item_path_to_activate:
            self.oled_display_manager.show_system_message("Nothing Cued", 1500, scroll_if_needed=False)
            return
        item_data = self._load_oled_item_data(item_path_to_activate)
        if item_data:
            item_name = item_data.get("item_name", "Item")
            item_type_label = item_data.get('type', '?')[:1].upper()
            
            self.active_graphic_item_relative_path = item_path_to_activate 
            self.oled_display_manager.set_active_graphic(item_data) 
            self._save_oled_config() 
            self.oled_display_manager.show_system_message(
                text=f"Active ({item_type_label}): {item_name}",
                duration_ms=1500,
                scroll_if_needed=True
            )
        else:
            self.oled_display_manager.show_system_message("Invalid Cue", 1500, scroll_if_needed=False)

    def action_play(self):  # Assuming this is animator play from MainWindow context
        if self.audio_visualizer_manager and self.audio_visualizer_manager.is_capturing:
            print("MW INFO: Animator play requested, stopping visualizer.")
            # Call _on_visualizer_enable_toggled(False) to correctly stop and update UI
            self._on_visualizer_enable_toggled(False)

        # Existing animator play logic
        if self.animator_manager:
            self.animator_manager.action_play()

    def _on_request_toggle_screen_sampler(self):
        # This method handles toggling the sampler.
        # If we are *starting* the sampler and visualizer is on, stop visualizer.
        if self.screen_sampler_manager:
            if not self.screen_sampler_manager.is_sampling_active():  # Sampler is about to be turned ON
                if self.audio_visualizer_manager and self.audio_visualizer_manager.is_capturing:
                    print(
                        "MW INFO: Sampler toggle (to ON) requested, stopping visualizer.")
                    self._on_visualizer_enable_toggled(False)

            # Now, toggle the sampler state
            self.screen_sampler_manager.toggle_sampling_state()
        else:
            self.status_bar.showMessage(
                "Sampler unavailable or controller disconnected.", 2000)

    def _on_request_cycle_sampler_monitor(self):
        """Handles hardware button press to cycle to the next sampler monitor."""
        if not self.screen_sampler_manager or not self.akai_controller.is_connected():
            self.status_bar.showMessage("Sampler unavailable or controller disconnected.", 2000)
            return        
        if not self.screen_sampler_manager.is_sampling_active():
            # Optionally, provide feedback that sampler needs to be on first
            if self.oled_display_manager and hasattr(self.oled_display_manager, 'show_temporary_message'):
                self.oled_display_manager.show_temporary_message("Enable Sampler", "to cycle monitors", 1500)
            else:
                self.status_bar.showMessage("Enable sampler first to cycle monitors.", 2000)
            return
        # print("MW TRACE: _on_request_cycle_sampler_monitor called.") # Optional
        self.screen_sampler_manager.cycle_target_monitor()
        # OLED feedback will be handled by connecting to screen_sampler_manager.sampler_monitor_changed

    def _on_sampler_monitor_cycled_for_oled(self, new_monitor_name: str):
        """Shows a temporary OLED message when the sampler monitor is cycled."""
        if not self.oled_display_manager:
            return
        display_name_part = new_monitor_name
        # Attempt to shorten "Monitor X (WxH)" to just "Monitor X" or "X"
        match = re.match(r"(Monitor\s*\d+)", display_name_part)
        if match:
            display_name_part = match.group(1)
        elif "Monitor" in display_name_part and "(" in display_name_part:
            try:
                display_name_part = display_name_part.split("(")[0].strip()
            except:
                pass
        self.oled_display_manager.show_system_message(
            text=f"Monitor: {display_name_part}",
            duration_ms=2000,
            scroll_if_needed=True
        )

    def _update_sampler_oled_feedback(self):
        """
        This method was for temporary sampler ON/OFF feedback.
        Its role is now largely handled by _on_sampler_activity_changed setting a
        persistent override message. It can be safely commented out or removed if
        _on_request_toggle_screen_sampler no longer relies on it for direct feedback.
        """
        # print("MW TRACE: _update_sampler_oled_feedback called - content is now handled by persistent override logic.") # Optional
        pass # Content is now managed by the persistent override in _on_sampler_activity_changed

    def _handle_grid_right_pressed(self):
        self._cycle_oled_nav_target(-1)

    def _finalize_navigation_action_ui_feedback(self):
        # print("MW TRACE: _finalize_navigation_action_ui_feedback called.") # Optional-
        self._is_hardware_nav_action_in_progress = False
        is_playing = False
        if self.animator_manager and self.animator_manager.active_sequence_model:
            is_playing = self.animator_manager.active_sequence_model.get_is_playing()
        self._update_fire_transport_leds(is_playing) 
        self._check_and_set_default_oled_text_if_idle()

    def _check_and_set_default_oled_text_if_idle(self):
        if self._oled_nav_interaction_active: return # Still actively navigating with encoder
        if self.oled_display_manager:
            # If a sequence is active, its name should be shown. Otherwise, default.
            if self.animator_manager and self.animator_manager.active_sequence_model and \
                self.animator_manager.active_sequence_model.name and \
                self.animator_manager.active_sequence_model.name != "New Sequence":
                is_mod = self.animator_manager.active_sequence_model.is_modified
                seq_name = self.animator_manager.active_sequence_model.name
                self._update_oled_and_title_on_sequence_change(is_mod, seq_name) # Let this handle "Untitled"
            else: # No active sequence name, revert to default
                self.oled_display_manager.set_display_text(None) # Triggers default in OLEDManager

    def _on_port_combo_changed(self, index: int):
        """Enables connect button if a valid port is selected and not already connected."""
        if not self.connect_button_direct_ref or not self.port_combo_direct_ref: return
        if not self.akai_controller.is_connected(): # Only change if not connected
            current_text = self.port_combo_direct_ref.itemText(index)
            can_connect = bool(current_text and current_text != "No MIDI output ports found")
            self.connect_button_direct_ref.setEnabled(can_connect)
        # else: self.connect_button_direct_ref.setEnabled(True) # If connected, button is "Disconnect"

    def toggle_connection(self):
        """Toggles MIDI connection state and handles initial OLED animation."""
        if self.akai_controller.is_connected() or self.akai_controller.is_input_connected():
            # --- DISCONNECT LOGIC ---
            if self.oled_display_manager and self.akai_controller.is_connected():
                self.oled_display_manager.clear_display_content()
            self.akai_controller.disconnect() # This handles both output and input
        else:
            # --- CONNECT LOGIC ---
            out_port = None
            if self.port_combo_direct_ref: # For MIDI Output port selection
                out_port = self.port_combo_direct_ref.currentText()
            
            # Use the internally stored and auto-selected MIDI input port name
            in_port_to_use = self._selected_midi_input_port_name 
            
            # Determine if we can attempt to connect input based on the selected name
            can_connect_in = bool(in_port_to_use and \
                                  in_port_to_use not in ["No MIDI input ports found", "Select MIDI Input", "", None]) # Added None check

            print(f"MW DEBUG toggle_connection: Attempting connect. Out: '{out_port}', Determined In: '{in_port_to_use}', CanConnectIn: {can_connect_in}")

            can_connect_out = bool(out_port and out_port != "No MIDI output ports found")
            
            if not can_connect_out:
                self.status_bar.showMessage("Please select a valid MIDI output port.", 3000)
                self.update_connection_status() # Update button states
                return

            # Pass the determined input port to the controller's connect method
            # AkaiFireController.connect() will call its own connect_input() if in_port_to_use is valid
            if self.akai_controller.connect(out_port, in_port_to_use if can_connect_in else None):
                # Success message
                status_msg = f"Successfully connected to Output: {self.akai_controller.port_name_used}"
                if self.akai_controller.is_input_connected() and self.akai_controller.in_port_name_used:
                    status_msg += f" | Input: {self.akai_controller.in_port_name_used}"
                self.status_bar.showMessage(status_msg, 2500)
                
                # OLED Startup Animation Logic (remains the same)
                if self.oled_display_manager:
                    if not self._has_played_initial_builtin_oled_animation:
                        try:
                            if MAIN_WINDOW_OLED_RENDERER_AVAILABLE:
                                startup_frames = oled_renderer.generate_fire_startup_animation()
                                if startup_frames:
                                    self.oled_display_manager.play_builtin_startup_animation(
                                        startup_frames, frame_duration_ms=60)
                                    self._has_played_initial_builtin_oled_animation = True
                                else:
                                    print("MW WARNING: Built-in startup animation generated no frames.")
                                    if hasattr(self, '_on_builtin_oled_startup_animation_finished'):
                                        self._on_builtin_oled_startup_animation_finished()
                                    elif hasattr(self.oled_display_manager, '_apply_current_oled_state'):
                                        self.oled_display_manager._apply_current_oled_state()
                            else:
                                print("MW WARNING: OLED Renderer not available, skipping built-in startup visual.")
                                self._has_played_initial_builtin_oled_animation = True
                                if hasattr(self.oled_display_manager, '_apply_current_oled_state'):
                                     self.oled_display_manager._apply_current_oled_state()
                        except Exception as e_anim:
                            print(f"MW ERROR: Could not generate/start OLED built-in startup animation: {e_anim}")
                            self._has_played_initial_builtin_oled_animation = True
                            if hasattr(self.oled_display_manager, '_apply_current_oled_state'):
                                self.oled_display_manager._apply_current_oled_state()
                    elif hasattr(self.oled_display_manager, '_apply_current_oled_state'): 
                        print("MW INFO: MIDI Reconnected. Triggering OLED state refresh.")
                        self.oled_display_manager._apply_current_oled_state()
            else:
                QMessageBox.warning(
                    self, "Connection Failed", f"Could not connect MIDI output to '{out_port}'" + 
                    (f" or input to '{in_port_to_use}'" if can_connect_in and in_port_to_use else "."))
        
        self.update_connection_status() # Update UI based on new connection state

    def _handle_fire_pad_event_INTERNAL(self, note: int, is_pressed: bool):
        # print(
        #     f"MW_PAD_ROUTER: Received Note {note} (0x{note:02X}), Pressed {is_pressed}, DOOM_ACTIVE: {self.is_doom_mode_active}")
        if self.is_doom_mode_active and self.doom_game_controller:
            # print(f"MW_PAD_ROUTER: Routing to DoomGameController.") # DEBUG
            self.doom_game_controller.handle_pad_event(note, is_pressed)
        else:
            pass

    def closeEvent(self, event: QCloseEvent): 
        # print("MW TRACE: closeEvent triggered.")
        if self.is_doom_mode_active:
            # If DOOM is active, exit it cleanly first before handling main app save prompts
            # print("MW TRACE: DOOM mode active during closeEvent, exiting DOOM mode first.")
            self._exit_doom_mode() 
            # Let event processing continue to allow animator save prompt if needed
        # Prompt to save unsaved animator changes (original logic)
        if self.animator_manager and self.animator_manager.active_sequence_model and \
            self.animator_manager.active_sequence_model.is_modified:
            reply = QMessageBox.question(self, "Unsaved Animator Changes",
                                        f"Animation '{self.animator_manager.active_sequence_model.name}' has unsaved changes. Save before exiting?",
                                        QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                        QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                save_success = self.animator_manager.action_save_sequence_as() # AMW shows dialog
                if not save_success: 
                    event.ignore() 
                    return 
            elif reply == QMessageBox.StandardButton.Cancel: 
                event.ignore() 
                return
        # Stop other managers and disconnect controller (original logic)
        if self.screen_sampler_manager: self.screen_sampler_manager.on_application_exit()
        if self.animator_manager: self.animator_manager.stop_current_animation_playback()
        if self.color_picker_manager: self.color_picker_manager.save_color_picker_swatches_to_config()        
        
        # --- ADDED: Stop Audio Visualizer ---
        if self.audio_visualizer_manager:
            self.audio_visualizer_manager.on_application_exit() # Call its cleanup
        # --- END ADDED ---

        if self.oled_display_manager:
            self.oled_display_manager.stop_all_activity() 
            if self.akai_controller and self.akai_controller.is_connected():
                self.oled_display_manager.clear_display_content() 
        if self.akai_controller and (self.akai_controller.is_connected() or self.akai_controller.is_input_connected()):
            self.akai_controller.disconnect()        
        print("MW INFO: Application closeEvent accepted.")
        super().closeEvent(event)
        # print("MW TRACE: closeEvent triggered.")
        if self.is_doom_mode_active:
            # If DOOM is active, exit it cleanly first before handling main app save prompts
            # print("MW TRACE: DOOM mode active during closeEvent, exiting DOOM mode first.")
            self._exit_doom_mode() 
            # Let event processing continue to allow animator save prompt if needed
        # Prompt to save unsaved animator changes (original logic)
        if self.animator_manager and self.animator_manager.active_sequence_model and \
            self.animator_manager.active_sequence_model.is_modified:
            reply = QMessageBox.question(self, "Unsaved Animator Changes",
                                        f"Animation '{self.animator_manager.active_sequence_model.name}' has unsaved changes. Save before exiting?",
                                        QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                        QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                save_success = self.animator_manager.action_save_sequence_as() # AMW shows dialog
                if not save_success: 
                    event.ignore() 
                    return 
            elif reply == QMessageBox.StandardButton.Cancel: 
                event.ignore() 
                return
        # Stop other managers and disconnect controller (original logic)
        if self.screen_sampler_manager: self.screen_sampler_manager.on_application_exit()
        if self.animator_manager: self.animator_manager.stop_current_animation_playback() # Should be safe to call even if stopped
        if self.color_picker_manager: self.color_picker_manager.save_color_picker_swatches_to_config()        
        if self.oled_display_manager:
            self.oled_display_manager.stop_all_activity() 
            if self.akai_controller and self.akai_controller.is_connected():
                self.oled_display_manager.clear_display_content() 
        if self.akai_controller and (self.akai_controller.is_connected() or self.akai_controller.is_input_connected()):
            self.akai_controller.disconnect()        
        print("MW INFO: Application closeEvent accepted.")
        super().closeEvent(event) # Call base class closeEvent