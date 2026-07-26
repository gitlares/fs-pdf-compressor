# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Native macOS Drop Zone for quick PDF compression."""

from __future__ import annotations

from pathlib import Path

import AppKit as AK
import Foundation as FN
import objc

try:
    import Quartz
except ImportError:  # Development environments may omit the Quartz bindings.
    Quartz = None


PANEL_WIDTH = 96.0
PANEL_HEIGHT = 96.0
PANEL_AUTOSAVE_NAME = "FS PDF Compressor Drop Zone v1"


def _desktop_window_level() -> int:
    if Quartz is None:
        return AK.NSNormalWindowLevel - 1
    return int(Quartz.CGWindowLevelForKey(Quartz.kCGDesktopIconWindowLevelKey) + 1)


class DropZoneView(AK.NSView):
    """Draw the hole and forward dropped filesystem URLs to the controller."""

    def initWithFrame_owner_(self, frame, owner):
        self = objc.super(DropZoneView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.owner = owner
        self.drag_active = False
        self.mode = "idle"
        self.progress = 0.0
        self.result_text = ""
        self.hole_image = self._load_hole_image()
        self.registerForDraggedTypes_([AK.NSPasteboardTypeFileURL])
        self.setAccessibilityLabel_("Drop Zone for PDF compression")
        return self

    def isOpaque(self):
        return False

    def _load_hole_image(self):
        resource = FN.NSBundle.mainBundle().pathForResource_ofType_(
            "desktop-drop-hole", "png"
        )
        if resource is None:
            local_asset = (
                Path(__file__).resolve().parents[1]
                / "assets"
                / "desktop-drop-hole.png"
            )
            resource = str(local_asset) if local_asset.is_file() else None
        if resource is None:
            return None
        return AK.NSImage.alloc().initWithContentsOfFile_(resource)

    def drawRect_(self, dirty_rect):
        bounds = self.bounds()
        center = AK.NSMakePoint(AK.NSMidX(bounds), AK.NSMidY(bounds))
        outer = AK.NSMakeRect(center.x - 38, center.y - 38, 76, 76)
        inner = AK.NSInsetRect(outer, 8, 8)

        if self.hole_image is not None:
            self.hole_image.drawInRect_fromRect_operation_fraction_respectFlipped_hints_(
                outer,
                AK.NSZeroRect,
                AK.NSCompositingOperationSourceOver,
                1.0,
                True,
                None,
            )
        else:
            AK.NSColor.blackColor().setFill()
            AK.NSBezierPath.bezierPathWithOvalInRect_(outer).fill()

        if self.drag_active:
            AK.NSColor.controlAccentColor().colorWithAlphaComponent_(0.76).setStroke()
            rim = AK.NSBezierPath.bezierPathWithOvalInRect_(outer)
            rim.setLineWidth_(2.0)
            rim.stroke()

        if self.mode == "processing":
            self._draw_progress(inner)
        elif self.mode == "result":
            self._draw_result(center)
        elif self.drag_active:
            self._draw_pdf_mark(center)

    def _draw_pdf_mark(self, center):
        style = AK.NSMutableParagraphStyle.alloc().init()
        style.setAlignment_(AK.NSTextAlignmentCenter)
        color = (
            AK.NSColor.controlAccentColor()
            if self.drag_active
            else AK.NSColor.whiteColor().colorWithAlphaComponent_(0.58)
        )
        attributes = {
            AK.NSFontAttributeName: AK.NSFont.monospacedSystemFontOfSize_weight_(
                11.0, AK.NSFontWeightSemibold
            ),
            AK.NSForegroundColorAttributeName: color,
            AK.NSKernAttributeName: 1.3,
            AK.NSParagraphStyleAttributeName: style,
        }
        FN.NSString.stringWithString_("PDF").drawInRect_withAttributes_(
            AK.NSMakeRect(center.x - 28, center.y - 7, 56, 16), attributes
        )

    def _draw_progress(self, inner):
        ring = AK.NSInsetRect(inner, 13, 13)
        AK.NSColor.whiteColor().colorWithAlphaComponent_(0.18).setStroke()
        background = AK.NSBezierPath.bezierPathWithOvalInRect_(ring)
        background.setLineWidth_(4)
        background.stroke()

        if self.progress <= 0:
            return
        start_angle = 90.0
        end_angle = start_angle - 360.0 * min(1.0, self.progress)
        AK.NSColor.controlAccentColor().setStroke()
        arc = AK.NSBezierPath.bezierPath()
        arc.setLineWidth_(4)
        arc.setLineCapStyle_(AK.NSLineCapStyleRound)
        arc.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_clockwise_(
            AK.NSMakePoint(AK.NSMidX(ring), AK.NSMidY(ring)),
            ring.size.width / 2,
            start_angle,
            end_angle,
            True,
        )
        arc.stroke()

    def _draw_result(self, center):
        style = AK.NSMutableParagraphStyle.alloc().init()
        style.setAlignment_(AK.NSTextAlignmentCenter)
        attributes = {
            AK.NSFontAttributeName: AK.NSFont.systemFontOfSize_weight_(
                12.0, AK.NSFontWeightSemibold
            ),
            AK.NSForegroundColorAttributeName: AK.NSColor.whiteColor().colorWithAlphaComponent_(
                0.86
            ),
            AK.NSParagraphStyleAttributeName: style,
        }
        FN.NSString.stringWithString_(self.result_text).drawInRect_withAttributes_(
            AK.NSMakeRect(center.x - 38, center.y - 9, 76, 18), attributes
        )

    def draggingEntered_(self, sender):
        self.drag_active = True
        self.setNeedsDisplay_(True)
        return AK.NSDragOperationCopy

    def draggingExited_(self, sender):
        self.drag_active = False
        self.setNeedsDisplay_(True)

    def prepareForDragOperation_(self, sender):
        return True

    def performDragOperation_(self, sender):
        self.drag_active = False
        pasteboard = sender.draggingPasteboard()
        urls = pasteboard.readObjectsForClasses_options_(
            [FN.NSURL], {AK.NSPasteboardURLReadingFileURLsOnlyKey: True}
        )
        paths = [str(url.path()) for url in (urls or []) if url.isFileURL()]
        accepted = self.owner.start_paths(paths)
        self.setNeedsDisplay_(True)
        return bool(accepted)

    def mouseDown_(self, event):
        if event.clickCount() == 2:
            self.owner.open_main_window()
            return
        self.window().performWindowDragWithEvent_(event)

    def set_processing(self):
        self.mode = "processing"
        self.progress = 0.03
        self.setNeedsDisplay_(True)

    def set_progress(self, completed, total):
        self.mode = "processing"
        self.progress = completed / total if total else 0.0
        self.setNeedsDisplay_(True)

    def set_result(self, text):
        self.mode = "result"
        self.result_text = text
        self.setNeedsDisplay_(True)

    def set_idle(self):
        self.mode = "idle"
        self.progress = 0.0
        self.result_text = ""
        self.setNeedsDisplay_(True)


class DropZonePanel(AK.NSPanel):
    """A passive, movable drop target that lives just above the desktop."""

    def initWithController_(self, controller):
        style = AK.NSWindowStyleMaskBorderless | AK.NSWindowStyleMaskNonactivatingPanel
        self = objc.super(
            DropZonePanel, self
        ).initWithContentRect_styleMask_backing_defer_(
            AK.NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT),
            style,
            AK.NSBackingStoreBuffered,
            False,
        )
        if self is None:
            return None
        self.controller = controller
        self.reset_timer = None
        self.setOpaque_(False)
        self.setBackgroundColor_(AK.NSColor.clearColor())
        self.setHasShadow_(False)
        self.setMovableByWindowBackground_(True)
        self.setHidesOnDeactivate_(False)
        self.setReleasedWhenClosed_(False)
        self.setExcludedFromWindowsMenu_(True)
        self.setLevel_(_desktop_window_level())
        self.setCollectionBehavior_(
            AK.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AK.NSWindowCollectionBehaviorStationary
            | AK.NSWindowCollectionBehaviorIgnoresCycle
        )
        self.view = DropZoneView.alloc().initWithFrame_owner_(
            AK.NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT), self
        )
        self.setContentView_(self.view)
        if not self.setFrameUsingName_(PANEL_AUTOSAVE_NAME):
            self._move_to_default_position()
        self.setFrameAutosaveName_(PANEL_AUTOSAVE_NAME)
        return self

    def _move_to_default_position(self):
        screen = AK.NSScreen.mainScreen()
        if screen is None:
            return
        visible = screen.visibleFrame()
        origin = AK.NSMakePoint(
            AK.NSMaxX(visible) - PANEL_WIDTH - 128,
            AK.NSMinY(visible) + 42,
        )
        self.setFrameOrigin_(origin)

    def start_paths(self, paths):
        if self.controller.processing:
            self._show_temporary_result("Busy")
            return False
        accepted = self.controller.start_drop_zone_paths(paths)
        if accepted:
            self.view.set_processing()
        else:
            self._show_temporary_result("PDF only")
        return accepted

    def open_main_window(self):
        self.controller.show_main_window()

    def show_panel(self):
        self.orderFrontRegardless()

    def batch_progress(self, completed, total):
        self.view.set_progress(completed, total)

    def batch_finished(self, summary):
        self._show_temporary_result(summary.compact_text if summary else "No change")

    def _show_temporary_result(self, text):
        self.view.set_result(text)
        if self.reset_timer is not None:
            self.reset_timer.invalidate()
        self.reset_timer = (
            FN.NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                2.4, self, "resetIndicator:", None, False
            )
        )

    def resetIndicator_(self, timer):
        self.reset_timer = None
        self.view.set_idle()
