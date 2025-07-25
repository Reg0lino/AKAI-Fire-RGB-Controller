# AKAI_Fire_PixelForge/gui/gif_region_selector.py
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QSize, QSizeF
from PyQt6.QtGui import QPainter, QPen, QColor, QCursor, QMouseEvent, QImage, QPixmap
from PIL.Image import Image
from PIL.ImageQt import ImageQt

class GifRegionSelectorLabel(QLabel):
    """
    A custom widget that manually draws a source image and a high-contrast,
    easy-to-use selection rectangle on top of it.
    """
    region_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._source_image: Image | None = None
        self.selection_rect_pct = QRectF(0.0, 0.0, 1.0, 1.0)
        self._is_dragging = False
        self._is_resizing = False
        self._resize_handle = None
        self._drag_start_pos = QPointF()
        # --- NEW: Define constants for better control ---
        self.handle_size = 10  # Slightly larger handles
        self.edge_margin = 6  # Pixel margin to detect edge resizing

    def set_image_to_display(self, pil_image: Image | None):
        self._source_image = pil_image
        self.set_full_region()
        self.update()

    def set_full_region(self):
        self.selection_rect_pct = QRectF(0.0, 0.0, 1.0, 1.0)
        self.region_changed.emit(
            {'x': 0.0, 'y': 0.0, 'width': 1.0, 'height': 1.0})
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        if self._source_image is None:
            painter.fillRect(self.rect(), QColor("#282828"))
            painter.setPen(Qt.GlobalColor.gray)
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
            return
        q_image = ImageQt(self._source_image)
        target_rect = self.rect().adjusted(5, 5, -5, -5)
        pixmap = QPixmap.fromImage(q_image)
        scaled_pixmap = pixmap.scaled(target_rect.size(
        ), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        pixmap_x = (target_rect.width() - scaled_pixmap.width()) / 2
        pixmap_y = (target_rect.height() - scaled_pixmap.height()) / 2
        self.pixmap_draw_rect = QRectF(
            pixmap_x, pixmap_y, scaled_pixmap.width(), scaled_pixmap.height())
        painter.drawPixmap(self.pixmap_draw_rect.toRect(), scaled_pixmap)
        selection_abs_rect = self._get_absolute_rect(self.selection_rect_pct)
        # --- NEW: High-contrast "marching ants" outline ---
        # 1. Draw black outline
        painter.setPen(QPen(Qt.GlobalColor.black, 3, Qt.PenStyle.SolidLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(selection_abs_rect)
        # 2. Draw white dashed line on top
        pen = QPen(Qt.GlobalColor.white, 1, Qt.PenStyle.DashLine)
        pen.setDashPattern([4, 4])  # 4px line, 4px gap
        painter.setPen(pen)
        painter.drawRect(selection_abs_rect)
        # Draw handles
        painter.setBrush(QColor(0, 120, 215, 200))
        painter.setPen(QPen(Qt.GlobalColor.white, 1))
        for handle_pos in self._get_handle_positions(selection_abs_rect).values():
            handle_rect = QRectF(handle_pos, QSizeF(
                self.handle_size, self.handle_size))
            painter.drawRect(handle_rect)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton or not hasattr(self, 'pixmap_draw_rect'):
            return
        pos = event.position()
        self._resize_handle = self._get_handle_at(pos)
        if self._resize_handle:
            self._is_resizing = True
        elif self._get_absolute_rect(self.selection_rect_pct).contains(pos):
            self._is_dragging = True
        elif self.pixmap_draw_rect.contains(pos):
            self._is_dragging, self._is_resizing = False, False
            start_pct = self._absolute_to_percentage(pos)
            self.selection_rect_pct = QRectF(start_pct, start_pct)
        else:
            return
        self._drag_start_pos = pos
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not hasattr(self, 'pixmap_draw_rect'):
            return
        pos = event.position()
        if event.buttons() & Qt.MouseButton.LeftButton:
            if self._is_resizing:
                self._resize_selection(pos)
            elif self._is_dragging:
                self._move_selection(pos)
            else:
                end_pct = self._absolute_to_percentage(pos)
                self.selection_rect_pct.setBottomRight(end_pct)
        handle = self._get_handle_at(pos)
        if handle:
            if handle in ('topLeft', 'bottomRight'):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif handle in ('topRight', 'bottomLeft'):
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif handle in ('top', 'bottom'):
                self.setCursor(Qt.CursorShape.SizeVerCursor)
            else:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif self._get_absolute_rect(self.selection_rect_pct).contains(pos):
            self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_dragging or self._is_resizing or self.selection_rect_pct.isNull():
                self._is_dragging = False
                self._is_resizing = False
                self._resize_handle = None
                self.setCursor(Qt.CursorShape.ArrowCursor)
                self.selection_rect_pct = self.selection_rect_pct.normalized()
                region_to_emit = {
                    'x': self.selection_rect_pct.x(), 'y': self.selection_rect_pct.y(),
                    'width': self.selection_rect_pct.width(), 'height': self.selection_rect_pct.height()
                }
                self.region_changed.emit(region_to_emit)
                self.update()

    # --- Helper methods ---
    def _get_absolute_rect(self, rect_pct: QRectF) -> QRectF:
        if not hasattr(self, 'pixmap_draw_rect'):
            return QRectF()
        x = self.pixmap_draw_rect.left() + (rect_pct.x() * self.pixmap_draw_rect.width())
        y = self.pixmap_draw_rect.top() + (rect_pct.y() * self.pixmap_draw_rect.height())
        w = rect_pct.width() * self.pixmap_draw_rect.width()
        h = rect_pct.height() * self.pixmap_draw_rect.height()
        return QRectF(x, y, w, h)

    def _absolute_to_percentage(self, pos: QPointF) -> QPointF:
        if not hasattr(self, 'pixmap_draw_rect') or self.pixmap_draw_rect.width() == 0 or self.pixmap_draw_rect.height() == 0:
            return QPointF(0, 0)
        x_pct = (pos.x() - self.pixmap_draw_rect.left()) / \
            self.pixmap_draw_rect.width()
        y_pct = (pos.y() - self.pixmap_draw_rect.top()) / \
            self.pixmap_draw_rect.height()
        return QPointF(max(0.0, min(x_pct, 1.0)), max(0.0, min(y_pct, 1.0)))

    def _get_handle_positions(self, rect_abs: QRectF):
        x, y, w, h = rect_abs.x(), rect_abs.y(), rect_abs.width(), rect_abs.height()
        hs = self.handle_size / 2
        return {'topLeft': QPointF(x-hs, y-hs), 'top': QPointF(x+w/2-hs, y-hs), 'topRight': QPointF(x+w-hs, y-hs),
                'left': QPointF(x-hs, y+h/2-hs), 'right': QPointF(x+w-hs, y+h/2-hs),
                'bottomLeft': QPointF(x-hs, y+h-hs), 'bottom': QPointF(x+w/2-hs, y+h-hs), 'bottomRight': QPointF(x+w-hs, y+h-hs)}

    def _get_handle_at(self, pos: QPointF):
        """Checks for handles and now also checks for edges."""
        rect_abs = self._get_absolute_rect(self.selection_rect_pct)
        # First, check corner and side handles for pixel-perfect precision
        for handle, handle_pos in self._get_handle_positions(rect_abs).items():
            if QRectF(handle_pos, QSizeF(self.handle_size, self.handle_size)).contains(pos):
                return handle
        # --- NEW: Check for edges if no handle was found ---
        on_top = abs(pos.y() - rect_abs.top()) < self.edge_margin
        on_bottom = abs(pos.y() - rect_abs.bottom()) < self.edge_margin
        on_left = abs(pos.x() - rect_abs.left()) < self.edge_margin
        on_right = abs(pos.x() - rect_abs.right()) < self.edge_margin
        in_horizontal_span = rect_abs.left() < pos.x() < rect_abs.right()
        in_vertical_span = rect_abs.top() < pos.y() < rect_abs.bottom()
        if on_top and in_horizontal_span:
            return 'top'
        if on_bottom and in_horizontal_span:
            return 'bottom'
        if on_left and in_vertical_span:
            return 'left'
        if on_right and in_vertical_span:
            return 'right'
        return None

    def _move_selection(self, pos: QPointF):
        delta = pos - self._drag_start_pos
        self._drag_start_pos = pos
        if self.pixmap_draw_rect.width() == 0 or self.pixmap_draw_rect.height() == 0:
            return
        delta_pct_x = delta.x() / self.pixmap_draw_rect.width()
        delta_pct_y = delta.y() / self.pixmap_draw_rect.height()
        new_x = self.selection_rect_pct.x() + delta_pct_x
        new_y = self.selection_rect_pct.y() + delta_pct_y
        new_x = max(0.0, min(new_x, 1.0 - self.selection_rect_pct.width()))
        new_y = max(0.0, min(new_y, 1.0 - self.selection_rect_pct.height()))
        self.selection_rect_pct.moveTo(new_x, new_y)

    def _resize_selection(self, pos: QPointF):
        pos_pct = self._absolute_to_percentage(pos)
        if self._resize_handle == 'topLeft':
            self.selection_rect_pct.setTopLeft(pos_pct)
        elif self._resize_handle == 'topRight':
            self.selection_rect_pct.setTopRight(pos_pct)
        elif self._resize_handle == 'bottomLeft':
            self.selection_rect_pct.setBottomLeft(pos_pct)
        elif self._resize_handle == 'bottomRight':
            self.selection_rect_pct.setBottomRight(pos_pct)
        elif self._resize_handle == 'top':
            self.selection_rect_pct.setTop(pos_pct.y())
        elif self._resize_handle == 'bottom':
            self.selection_rect_pct.setBottom(pos_pct.y())
        elif self._resize_handle == 'left':
            self.selection_rect_pct.setLeft(pos_pct.x())
        elif self._resize_handle == 'right': self.selection_rect_pct.setRight(pos_pct.x())