from typing import Tuple
import time

import keyboard
import numpy as np
from PIL import Image, ImageDraw
from Quartz import (
    CGDataProviderCopyData,
    CGDisplayBounds,
    CGDisplayCreateImage,
    CGDisplayCreateImageForRect,
    CGEventCreateKeyboardEvent,
    CGEventCreateMouseEvent,
    CGEventPost,
    CGEventSetFlags,
    CGEventSourceKeyState,
    CGRectMake,
    CGImageGetBytesPerRow,
    CGImageGetDataProvider,
    CGImageGetHeight,
    CGImageGetWidth,
    CGMainDisplayID,
    CGWindowListCreateImage,
    CGPoint,
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskShift,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseUp,
    kCGEventMouseMoved,
    kCGEventSourceStateHIDSystemState,
    kCGHIDEventTap,
    kCGMouseButtonLeft,
    kCGNullWindowID,
    kCGWindowImageDefault,
    kCGWindowListOptionOnScreenOnly,
)
from AppKit import NSPasteboard, NSPasteboardTypeString

SPACE_KEYCODE = 49  # macOS virtual keycode for space
KEYCODE_MAP = {
    "c": 8,
    "v": 9,
    "n": 45,
}

def is_space_pressed() -> bool:
    """
    Return True if the space bar is currently held down (Quartz query, no sudo).
    """
    try:
        return bool(CGEventSourceKeyState(kCGEventSourceStateHIDSystemState, SPACE_KEYCODE))
    except Exception:
        # Be resilient if Quartz is unavailable
        return False


def _send_keys_quartz(keys: list[str]) -> None:
    """
    Send a hotkey using Quartz (no sudo). Supports one main key + modifiers.
    """
    if not keys:
        return

    flags = 0
    keycode = None
    for k in keys:
        lk = k.lower()
        if lk in ("cmd", "command", "meta", "super"):
            flags |= kCGEventFlagMaskCommand
        elif lk in ("alt", "option", "opt"):
            flags |= kCGEventFlagMaskAlternate
        elif lk in ("ctrl", "control", "ctl"):
            flags |= kCGEventFlagMaskControl
        elif lk == "shift":
            flags |= kCGEventFlagMaskShift
        else:
            if keycode is not None:
                raise ValueError("Only one primary key supported in hotkey.")
            keycode = KEYCODE_MAP.get(lk)

    if keycode is None:
        raise ValueError("No primary key specified for hotkey.")

    down = CGEventCreateKeyboardEvent(None, keycode, True)
    up = CGEventCreateKeyboardEvent(None, keycode, False)
    if flags:
        CGEventSetFlags(down, flags)
        CGEventSetFlags(up, flags)

    CGEventPost(kCGHIDEventTap, down)
    CGEventPost(kCGHIDEventTap, up)


class worker:
    def __init__(self):
        self.last_gray = None
        self.last_x = None
        self.last_y = None
        self.copyKey = [
            "command", "c"
        ]
        self.pasteKey = [
            "command", "v"
        ]
        self.startKey = [
            "option", "command", "n"
        ]

    @staticmethod
    def is_space_pressed() -> bool:
        """
        Return True if the space bar is currently held down (uses Quartz, no sudo).
        """
        try:
            return is_space_pressed()
        except Exception:
            # Be resilient if Quartz is unavailable
            return False
        
    def capture_main_display_gray(self, label: str = "") -> np.ndarray:
        """
        Capture the current main display, convert it to grayscale, and return as a NumPy array.
        Raises RuntimeError if the capture fails.
        """
        display_id = CGMainDisplayID()
        bounds = CGDisplayBounds(display_id)
        image_ref = CGWindowListCreateImage(
            bounds, kCGWindowListOptionOnScreenOnly, kCGNullWindowID, kCGWindowImageDefault
        )
        if image_ref is None:
            raise RuntimeError("Failed to capture main display.")

        width = CGImageGetWidth(image_ref)
        height = CGImageGetHeight(image_ref)
        bytes_per_row = CGImageGetBytesPerRow(image_ref)
        provider = CGImageGetDataProvider(image_ref)
        data = CGDataProviderCopyData(provider)

        # Raw buffer is BGRA; Pillow understands the channel order when specified.
        raw = bytes(data)
        img = Image.frombuffer(
            "RGBA",
            (width, height),
            raw,
            "raw",
            "BGRA",
            bytes_per_row,
            1,
        )
        img.save(f"screenshot_main_{label}_{int(time.time()*1000)}.png")
        gray = img.convert("L")  # Convert to grayscale
        return np.array(gray)


    def find_max_diff_center(self, mat_a: np.ndarray, mat_b: np.ndarray, window: int = 99) -> Tuple[int, int]:
        """
        在 mat_a 中寻找接近全白且在 mat_b 中新增大量黑色文字的窗口中心（x, y）。
        默认返回窗口中心坐标（x, y）。
        """
        if mat_a.shape != mat_b.shape:
            raise ValueError("Input matrices must have the same shape.")
        if window % 2 == 0 or window < 1:
            raise ValueError("Window size must be a positive odd integer.")
        if mat_a.shape[0] < window or mat_a.shape[1] < window:
            raise ValueError("Window size is larger than the provided matrices.")

        # Tunables: what counts as "almost white" in A and "black text" in B.
        white_threshold = 245  # higher = closer to pure white
        black_threshold = 60   # lower = darker pixels considered text

        area = window * window

        def integral_image(arr: np.ndarray) -> np.ndarray:
            padded = np.pad(arr, ((1, 0), (1, 0)), mode="constant", constant_values=0)
            return padded.cumsum(axis=0).cumsum(axis=1)

        def window_sums(integral: np.ndarray) -> np.ndarray:
            w = window
            return (
                integral[w:, w:]
                - integral[:-w, w:]
                - integral[w:, :-w]
                + integral[:-w, :-w]
            )

        # Mean brightness in A (higher -> whiter).
        integral_a = integral_image(mat_a.astype(np.int64))
        mean_a = window_sums(integral_a) / float(area)

        # Count of dark pixels in B (higher -> more black text).
        dark_mask_b = (mat_b <= black_threshold).astype(np.int64)
        integral_dark = integral_image(dark_mask_b)
        dark_count = window_sums(integral_dark)

        # Score: only consider windows where A is near white; prefer more dark pixels in B.
        whiteness = np.clip((mean_a - white_threshold) / (255 - white_threshold), 0.0, 1.0)
        density = dark_count / float(area)
        score = whiteness * density

        # Restrict search to central 20%~80% region to avoid edges.
        h_ws, w_ws = score.shape
        y0 = max(0, int(h_ws * 0.2))
        y1 = max(y0 + 1, int(h_ws * 0.8))
        x0 = max(0, int(w_ws * 0.2))
        x1 = max(x0 + 1, int(w_ws * 0.8))

        roi = score[y0:y1, x0:x1]
        if roi.size == 0:
            raise ValueError("ROI for max search is empty.")

        local_idx = np.unravel_index(np.argmax(roi), roi.shape)
        top = y0 + local_idx[0]
        left = x0 + local_idx[1]
        center_y = top + window // 2
        center_x = left + window // 2
        self.max_diff_center_x = int(center_x)
        self.max_diff_center_y = int(center_y)
        return int(center_x), int(center_y)
    
    def get_greatest_diff_value(self, mat_a: np.ndarray, mat_b: np.ndarray) -> int:
        """
        Given two grayscale matrices, find the value with the greatest absolute difference.
        """
        diff = np.abs(mat_a.astype(np.int64) - mat_b.astype(np.int64))
        return np.max(diff)
    
    


    def move_and_click(self, x: int, y: int) -> None:
        """
        Move the mouse to the given screen coordinate and perform a single left click.
        Coordinates are expected in the usual screen space (origin at top-left).
        """
        display_id = CGMainDisplayID()
        bounds = CGDisplayBounds(display_id)

        # Use pixel dimensions (Retina-safe) to stay consistent with screenshot-based coords.
        image_ref = CGDisplayCreateImage(display_id)
        if image_ref is None:
            raise RuntimeError("Failed to capture display for click.")

        pixel_w = float(CGImageGetWidth(image_ref))
        pixel_h = float(CGImageGetHeight(image_ref))
        point_w = float(bounds.size.width)
        point_h = float(bounds.size.height)

        scale_x = pixel_w / point_w if point_w else 1.0
        scale_y = pixel_h / point_h if point_h else 1.0

        x_pt = x / scale_x
        y_pt = y / scale_y

        # macOS mouse event coordinates are already top-left–origin in practice; do not flip.
        flipped_point = CGPoint(x_pt, y_pt)

        move_event = CGEventCreateMouseEvent(None, kCGEventMouseMoved, flipped_point, kCGMouseButtonLeft)
        down_event = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, flipped_point, kCGMouseButtonLeft)
        up_event = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, flipped_point, kCGMouseButtonLeft)

        for evt in (move_event, down_event, up_event):
            CGEventPost(kCGHIDEventTap, evt)

        # After clicking, capture full screenshot and draw a red 100x100 box at the click center.
        self._save_full_screenshot_with_marker(x, y, size=100)

    def _capture_region_centered(self, x: int, y: int, size: int = 100, path: str | None = None) -> str:
        """
        Capture a square region centered at (x, y) and save to disk.
        Returns the saved file path.
        """
        display_id = CGMainDisplayID()
        bounds = CGDisplayBounds(display_id)
        screen_w = int(bounds.size.width)
        screen_h = int(bounds.size.height)

        half = size // 2
        left = max(0, x - half)
        top = max(0, y - half)
        # Clamp width/height so the rect stays on-screen.
        width = min(size, screen_w - left)
        height = min(size, screen_h - top)

        rect = CGRectMake(left, top, width, height)
        image_ref = CGDisplayCreateImageForRect(display_id, rect)
        if image_ref is None:
            image_ref = CGWindowListCreateImage(
                rect, kCGWindowListOptionOnScreenOnly, kCGNullWindowID, kCGWindowImageDefault
            )
        if image_ref is None:
            raise RuntimeError("Failed to capture click region.")

        bytes_per_row = CGImageGetBytesPerRow(image_ref)
        provider = CGImageGetDataProvider(image_ref)
        data = CGDataProviderCopyData(provider)

        raw = bytes(data)
        img = Image.frombuffer(
            "RGBA",
            (CGImageGetWidth(image_ref), CGImageGetHeight(image_ref)),
            raw,
            "raw",
            "BGRA",
            bytes_per_row,
            1,
        )

        # Drop alpha to avoid transparent PNG if screen-recording gives premultiplied alpha.
        img = img.convert("RGB")

        if path is None:
            path = f"click_region_{int(time.time()*1000)}.png"
        img.save(path)
        return path

    def _save_full_screenshot_with_marker(self, x: int, y: int, size: int = 100, path: str | None = None) -> str:
        """
        Capture the full screen and draw a red square (size x size) centered at (x, y).
        Saves to disk and returns the path.
        """
        display_id = CGMainDisplayID()
        image_ref = CGDisplayCreateImage(display_id)
        if image_ref is None:
            raise RuntimeError("Failed to capture full screen.")

        bytes_per_row = CGImageGetBytesPerRow(image_ref)
        provider = CGImageGetDataProvider(image_ref)
        data = CGDataProviderCopyData(provider)

        raw = bytes(data)
        img = Image.frombuffer(
            "RGBA",
            (CGImageGetWidth(image_ref), CGImageGetHeight(image_ref)),
            raw,
            "raw",
            "BGRA",
            bytes_per_row,
            1,
        ).convert("RGB")

        draw = ImageDraw.Draw(img)
        half = size // 2
        left = max(0, x - half)
        top = max(0, y - half)
        right = min(img.width - 1, x + half)
        bottom = min(img.height - 1, y + half)
        draw.rectangle([left, top, right, bottom], outline=(255, 0, 0), width=3)

        if path is None:
            path = f"click_full_{int(time.time()*1000)}.png"
        img.save(path)
        return path


    def capture_iupac_block(
        self,
        white_threshold: int = 245,
        min_pixels: int = 2000,
        margin: int = 3,
        path: str | None = None,
    ) -> Tuple[Tuple[int, int, int, int], str]:
        """
        Capture the screen, find a black-text-on-white block, save the cropped region.
        Returns (bbox, saved_path).
        """
        gray = self.capture_main_display_gray()
        bbox = self.locate_white_bg_black_text(
            gray, white_threshold=white_threshold, min_pixels=min_pixels, margin=margin
        )
        left, top, right, bottom = bbox
        crop = Image.fromarray(gray).crop((left, top, right, bottom)).convert("RGB")
        if path is None:
            path = f"iupac_block_{int(time.time()*1000)}.png"
        crop.save(path)
        return bbox, path


    def press_keys(self, keys: list[str]) -> None:
        """
        按下并释放给定的按键序列（先按下全部，再按相反顺序释放）。
        需要已获得辅助功能/键盘权限。
        """
        if not keys:
            return

        print('+'.join(keys))
        try:
            _send_keys_quartz(keys)
        except Exception:
            # Fallback to keyboard library if Quartz fails for any reason.
            keyboard.press_and_release('+'.join(keys))

    def get_clipboard_text(self) -> str:
        """
        Return current clipboard text content; empty string if unavailable.
        """
        pb = NSPasteboard.generalPasteboard()
        if pb is None:
            raise RuntimeError("无法访问系统剪贴板（NSPasteboard 为 None）")
        content = pb.stringForType_(NSPasteboardTypeString)
        return content if content is not None else ""

    def write_to_clipboard(self, text: str) -> None:
        """
        Write the given text to the clipboard.
        """
        pb = NSPasteboard.generalPasteboard()
        if pb is None:
            raise RuntimeError("无法访问系统剪贴板（NSPasteboard 为 None）")
        pb.declareTypes_owner_([NSPasteboardTypeString], None)
        pb.setString_forType_(text, NSPasteboardTypeString)