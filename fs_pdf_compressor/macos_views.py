# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""AppKit views used by the main FS PDF Compressor window."""

from __future__ import annotations

import AppKit as AK
import Foundation as FN
import objc


class DropCanvas(AK.NSView):
    def initWithFrame_controller_(self, frame, controller):
        self = objc.super(DropCanvas, self).initWithFrame_(frame)
        if self is None:
            return None
        self.controller = controller
        self.drag_active = False
        self.registerForDraggedTypes_([AK.NSPasteboardTypeFileURL])
        return self

    def drawRect_(self, dirty_rect):
        bounds = self.bounds()
        AK.NSColor.windowBackgroundColor().setFill()
        AK.NSBezierPath.fillRect_(bounds)

        if self.controller.showing_results:
            return

        footer_height = self.controller.FOOTER_HEIGHT
        available_height = max(0.0, bounds.size.height - footer_height)
        side = min(188.0, bounds.size.width * 0.34, available_height * 0.56)
        target = AK.NSMakeRect(
            (bounds.size.width - side) / 2,
            footer_height + (available_height - side) / 2,
            side,
            side,
        )

        border_color = (
            AK.NSColor.controlAccentColor().colorWithAlphaComponent_(0.55)
            if self.drag_active
            else AK.NSColor.quaternaryLabelColor()
        )
        border_color.setStroke()
        border = AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            target, 19, 19
        )
        border.setLineWidth_(2.0)
        border.setLineDash_count_phase_([7.0, 6.0], 2, 0.0)
        border.stroke()

        arrow_color = (
            AK.NSColor.controlAccentColor().colorWithAlphaComponent_(0.72)
            if self.drag_active
            else AK.NSColor.tertiaryLabelColor()
        )
        arrow_color.setStroke()
        center_x = AK.NSMidX(target)
        center_y = AK.NSMidY(target)
        arrow = AK.NSBezierPath.bezierPath()
        arrow.setLineWidth_(3.0)
        arrow.setLineCapStyle_(AK.NSLineCapStyleRound)
        arrow.setLineJoinStyle_(AK.NSLineJoinStyleRound)
        arrow.moveToPoint_(AK.NSMakePoint(center_x, center_y + 36))
        arrow.lineToPoint_(AK.NSMakePoint(center_x, center_y - 23))
        arrow.moveToPoint_(AK.NSMakePoint(center_x - 21, center_y - 3))
        arrow.lineToPoint_(AK.NSMakePoint(center_x, center_y - 25))
        arrow.lineToPoint_(AK.NSMakePoint(center_x + 21, center_y - 3))
        arrow.stroke()

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
        self.setNeedsDisplay_(True)
        pasteboard = sender.draggingPasteboard()
        urls = pasteboard.readObjectsForClasses_options_(
            [FN.NSURL], {AK.NSPasteboardURLReadingFileURLsOnlyKey: True}
        )
        self.controller.handle_drop_urls(urls or [])
        return bool(urls)


class ResultsTableView(AK.NSView):
    """Result table for completed PDF batches."""

    ROW_HEIGHT = 40.0
    HEADER_HEIGHT = 34.0
    INSET = 12.0

    def initWithController_(self, controller):
        self = objc.super(ResultsTableView, self).initWithFrame_(AK.NSZeroRect)
        if self is None:
            return None
        self.controller = controller
        return self

    def isFlipped(self):
        return True

    def requiredHeightForWidth_(self, width):
        rows = max(1, len(self.controller.statuses))
        return self.INSET * 2 + self.HEADER_HEIGHT + rows * self.ROW_HEIGHT

    def _draw_text(self, value, rect, font, color, alignment=AK.NSTextAlignmentLeft):
        style = AK.NSMutableParagraphStyle.alloc().init()
        style.setAlignment_(alignment)
        style.setLineBreakMode_(AK.NSLineBreakByTruncatingMiddle)
        attributes = {
            AK.NSFontAttributeName: font,
            AK.NSForegroundColorAttributeName: color,
            AK.NSParagraphStyleAttributeName: style,
        }
        FN.NSString.stringWithString_(value).drawInRect_withAttributes_(
            rect, attributes
        )

    def drawRect_(self, dirty_rect):
        bounds = self.bounds()
        card = AK.NSMakeRect(
            self.INSET,
            self.INSET,
            max(0, bounds.size.width - self.INSET * 2),
            min(
                max(0, bounds.size.height - self.INSET * 2),
                self.HEADER_HEIGHT
                + max(1, len(self.controller.statuses)) * self.ROW_HEIGHT,
            ),
        )
        AK.NSColor.controlBackgroundColor().setFill()
        AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(card, 12, 12).fill()

        heading_font = AK.NSFont.systemFontOfSize_weight_(10.0, AK.NSFontWeightSemibold)
        body_font = AK.NSFont.systemFontOfSize_(13.0)
        value_font = AK.NSFont.monospacedDigitSystemFontOfSize_weight_(
            13.0, AK.NSFontWeightMedium
        )
        muted = AK.NSColor.secondaryLabelColor()
        ink = AK.NSColor.labelColor()
        accent = AK.NSColor.systemGreenColor()
        row_left = card.origin.x + 14
        row_right = card.origin.x + card.size.width - 14
        value_width = 104
        header_y = card.origin.y + 8
        self._draw_text(
            "FILE",
            AK.NSMakeRect(row_left, header_y, 240, 14),
            heading_font,
            muted,
        )
        self._draw_text(
            "REDUCTION",
            AK.NSMakeRect(row_right - value_width, header_y, value_width, 14),
            heading_font,
            muted,
            AK.NSTextAlignmentRight,
        )

        separator_y = card.origin.y + self.HEADER_HEIGHT
        AK.NSColor.separatorColor().setStroke()
        line = AK.NSBezierPath.bezierPath()
        line.moveToPoint_(AK.NSMakePoint(row_left, separator_y))
        line.lineToPoint_(AK.NSMakePoint(row_right, separator_y))
        line.setLineWidth_(1)
        line.stroke()

        for index, status in enumerate(self.controller.statuses):
            row_y = separator_y + index * self.ROW_HEIGHT
            filename, marker, result = status.partition("   ↓ ")
            if marker:
                detail = f"↓ {result}"
                detail_color = accent
            else:
                filename, separator, detail = status.partition(" — ")
                detail = detail if separator else "Waiting"
                detail_color = muted
            self._draw_text(
                filename,
                AK.NSMakeRect(
                    row_left,
                    row_y + 11,
                    max(60, card.size.width - value_width - 40),
                    18,
                ),
                body_font,
                ink,
            )
            self._draw_text(
                detail,
                AK.NSMakeRect(row_right - value_width, row_y + 11, value_width, 18),
                value_font,
                detail_color,
                AK.NSTextAlignmentRight,
            )
            if index < len(self.controller.statuses) - 1:
                AK.NSColor.separatorColor().setStroke()
                row_line = AK.NSBezierPath.bezierPath()
                row_line.moveToPoint_(AK.NSMakePoint(row_left, row_y + self.ROW_HEIGHT))
                row_line.lineToPoint_(
                    AK.NSMakePoint(row_right, row_y + self.ROW_HEIGHT)
                )
                row_line.setLineWidth_(1)
                row_line.stroke()
