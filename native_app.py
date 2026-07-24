# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

import glob
import logging
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import AppKit as AK
import Foundation as FN
import objc
from PyObjCTools import AppHelper


APP_NAME = "FS PDF Compressor"
APP_VERSION = os.environ.get("APP_VERSION", "1.0.5")
REPOSITORY_URL = "https://github.com/gitlares/fs-pdf-compressor"
CONTRIBUTE_URL = f"{REPOSITORY_URL}/blob/main/CONTRIBUTING.md"
DONATE_URL = "https://www.paypal.com/donate/?hosted_button_id=7RDCBR3QXXEMJ"


QUALITY_PROFILES = [
    (
        "Preserve quality (minimal loss)",
        "/prepress",
        "Keeps print resolution and quality; the file may shrink only slightly.",
    ),
    (
        "Balanced (recommended)",
        "/ebook",
        "Reduces file size while keeping good on-screen quality.",
    ),
    (
        "Maximum compression",
        "/screen",
        "Creates a smaller file with greater visual quality loss.",
    ),
]

QUALITY_CONTROL_LABELS = ("Preserve", "Balanced", "Maximum")
LOG_PATH = Path.home() / "Library" / "Logs" / APP_NAME / "compression.log"


def compression_logger():
    """Return a local-only error log without sending document data anywhere."""
    logger = logging.getLogger("fs_pdf_compressor")
    if logger.handlers:
        return logger
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    except OSError:
        logger.addHandler(logging.NullHandler())
    return logger


def load_sparkle_updater():
    """Load the bundled Sparkle framework without making it a Python dependency."""
    contents_dir = bundle_contents_dir()
    if contents_dir is None:
        return None
    framework = contents_dir / "Frameworks" / "Sparkle.framework"
    if not framework.is_dir():
        return None
    try:
        objc.loadBundle("Sparkle", globals(), bundle_path=str(framework))
        controller_class = objc.lookUpClass("SPUStandardUpdaterController")
        return controller_class.alloc().initWithStartingUpdater_updaterDelegate_userDriverDelegate_(
            True, None, None
        )
    except Exception:
        compression_logger().exception("Could not initialize the Sparkle updater")
        return None


def get_file_size_kb(path):
    return os.path.getsize(path) / 1024


def format_file_size(byte_count):
    if byte_count >= 1_000_000:
        return f"{byte_count / 1_000_000:.1f} MB"
    return f"{byte_count / 1_000:.0f} KB"


def compressed_copy_path(original_path):
    path = Path(original_path)
    candidate = path.with_name(f"{path.stem} compressed{path.suffix}")
    sequence = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} compressed {sequence}{path.suffix}")
        sequence += 1
    return str(candidate)


def bundle_contents_dir():
    executable = Path(sys.executable).resolve()
    for parent in executable.parents:
        if parent.name == "Contents":
            return parent
    return None


def get_ghostscript_config():
    contents_dir = bundle_contents_dir()
    if contents_dir:
        bundled_root = contents_dir / "Resources" / "ghostscript"
        bundled_gs = bundled_root / "bin" / "gs"
        if bundled_gs.is_file() and os.access(bundled_gs, os.X_OK):
            environment = os.environ.copy()
            resource_root = bundled_root / "share" / "ghostscript"
            environment["GS_LIB"] = os.pathsep.join(
                str(path)
                for path in (
                    resource_root / "Resource" / "Init",
                    resource_root / "Resource",
                    resource_root / "lib",
                    resource_root / "fonts",
                )
                if path.exists()
            )
            bundled_libraries = contents_dir / "Frameworks" / "Ghostscript"
            environment["DYLD_FALLBACK_LIBRARY_PATH"] = str(bundled_libraries)
            return str(bundled_gs), environment

    for candidate in (
        shutil.which("gs"),
        "/opt/homebrew/bin/gs",
        "/usr/local/bin/gs",
    ):
        if candidate and os.path.exists(candidate):
            return candidate, os.environ.copy()
    return None, os.environ.copy()


def compress_pdf(original_path, pdf_settings, keep_original):
    filename = os.path.basename(original_path)
    logger = compression_logger()
    temp_path = original_path + ".temp.pdf"
    try:
        gs_path, gs_environment = get_ghostscript_config()
        if not gs_path:
            logger.error("Ghostscript was unavailable while compressing %s", filename)
            return f"{filename} — Ghostscript unavailable", None

        original_size = os.path.getsize(original_path)
        result = subprocess.run(
            [
                gs_path,
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                f"-dPDFSETTINGS={pdf_settings}",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                f"-sOutputFile={temp_path}",
                original_path,
            ],
            env=gs_environment,
            capture_output=True,
        )
        if result.returncode != 0 or not os.path.exists(temp_path):
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            logger.error("Ghostscript failed for %s (exit %s): %s", filename, result.returncode, detail)
            return f"{filename} — compression failed", None

        new_size = os.path.getsize(temp_path)
        if new_size >= original_size:
            os.unlink(temp_path)
            return f"{filename} — no size reduction", None

        output_path = compressed_copy_path(original_path) if keep_original else original_path
        os.replace(temp_path, output_path)
        reduction = 100 - (new_size / original_size * 100)
        return (
            f"{os.path.basename(output_path)}   ↓ {reduction:.1f}%",
            {"original_size": original_size, "saved_size": original_size - new_size},
        )
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        logger.exception("Unexpected compression failure for %s", filename)
        return f"{filename} — compression failed", None


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
        border = AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(target, 19, 19)
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
    """A small, purpose-built result table for completed PDF batches."""

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
        FN.NSString.stringWithString_(value).drawInRect_withAttributes_(rect, attributes)

    def drawRect_(self, dirty_rect):
        bounds = self.bounds()
        card = AK.NSMakeRect(
            self.INSET,
            self.INSET,
            max(0, bounds.size.width - self.INSET * 2),
            min(
                max(0, bounds.size.height - self.INSET * 2),
                self.HEADER_HEIGHT + max(1, len(self.controller.statuses)) * self.ROW_HEIGHT,
            ),
        )
        AK.NSColor.controlBackgroundColor().setFill()
        AK.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(card, 12, 12).fill()

        heading_font = AK.NSFont.systemFontOfSize_weight_(10.0, AK.NSFontWeightSemibold)
        body_font = AK.NSFont.systemFontOfSize_(13.0)
        value_font = AK.NSFont.monospacedDigitSystemFontOfSize_weight_(13.0, AK.NSFontWeightMedium)
        muted = AK.NSColor.secondaryLabelColor()
        ink = AK.NSColor.labelColor()
        accent = AK.NSColor.systemGreenColor()
        row_left = card.origin.x + 14
        row_right = card.origin.x + card.size.width - 14
        value_width = 104
        header_y = card.origin.y + 8
        self._draw_text("FILE", AK.NSMakeRect(row_left, header_y, 240, 14), heading_font, muted)
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
                AK.NSMakeRect(row_left, row_y + 11, max(60, card.size.width - value_width - 40), 18),
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
                row_line.lineToPoint_(AK.NSMakePoint(row_right, row_y + self.ROW_HEIGHT))
                row_line.setLineWidth_(1)
                row_line.stroke()


class PDFCompressorController(FN.NSObject):
    # Mirror the quiet, compact control strip shown on the public site preview.
    FOOTER_HEIGHT = 52.0

    def init(self):
        self = objc.super(PDFCompressorController, self).init()
        if self is None:
            return None
        self.pdf_files = []
        self.statuses = []
        self.metrics = []
        self.quality_index = 1
        self.showing_results = False
        self.processing = False
        self._build_window()
        return self

    def _build_window(self):
        style = (
            AK.NSWindowStyleMaskTitled
            | AK.NSWindowStyleMaskClosable
            | AK.NSWindowStyleMaskMiniaturizable
            | AK.NSWindowStyleMaskResizable
        )
        self.window = AK.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            AK.NSMakeRect(0, 0, 680, 430), style, AK.NSBackingStoreBuffered, False
        )
        self.window.setTitle_(APP_NAME)
        self.window.setMinSize_(AK.NSMakeSize(620, 380))
        self.window.setDelegate_(self)
        self.window.center()

        self.canvas = DropCanvas.alloc().initWithFrame_controller_(
            AK.NSMakeRect(0, 0, 680, 430), self
        )
        self.window.setContentView_(self.canvas)

        self.results_scroll = AK.NSScrollView.alloc().initWithFrame_(AK.NSZeroRect)
        self.results_scroll.setBorderType_(AK.NSNoBorder)
        self.results_scroll.setHasVerticalScroller_(True)
        self.results_scroll.setAutohidesScrollers_(True)
        self.results_scroll.setDrawsBackground_(False)
        self.results_scroll.setHidden_(True)
        self.results_table = ResultsTableView.alloc().initWithController_(self)
        self.results_scroll.setDocumentView_(self.results_table)
        self.canvas.addSubview_(self.results_scroll)

        self.footer = AK.NSVisualEffectView.alloc().initWithFrame_(AK.NSZeroRect)
        self.footer.setMaterial_(AK.NSVisualEffectMaterialUnderWindowBackground)
        self.footer.setBlendingMode_(AK.NSVisualEffectBlendingModeWithinWindow)
        self.footer.setState_(AK.NSVisualEffectStateFollowsWindowActiveState)
        self.canvas.addSubview_(self.footer)

        self.separator = AK.NSBox.alloc().initWithFrame_(AK.NSZeroRect)
        self.separator.setBoxType_(AK.NSBoxSeparator)
        self.footer.addSubview_(self.separator)

        self.add_button = AK.NSButton.alloc().initWithFrame_(AK.NSZeroRect)
        self.add_button.setBezelStyle_(AK.NSBezelStyleRounded)
        self.add_button.setControlSize_(AK.NSControlSizeSmall)
        self.add_button.setImage_(
            AK.NSImage.imageWithSystemSymbolName_accessibilityDescription_("plus", "Add")
        )
        self.add_button.setImagePosition_(AK.NSImageOnly)
        self.add_button.setToolTip_("Choose PDF files")
        self.add_button.setTarget_(self)
        self.add_button.setAction_("chooseFiles:")
        self.footer.addSubview_(self.add_button)

        self.status_label = AK.NSTextField.labelWithString_("Drag PDFs to the area above")
        self.status_label.setFont_(AK.NSFont.systemFontOfSize_(12.0))
        self.status_label.setLineBreakMode_(AK.NSLineBreakByTruncatingTail)
        self.footer.addSubview_(self.status_label)

        self.keep_original = AK.NSButton.checkboxWithTitle_target_action_(
            "Keep original", self, None
        )
        self.keep_original.setControlSize_(AK.NSControlSizeSmall)
        self.keep_original.setToolTip_(
            "Saves “name compressed.pdf” without modifying the original PDF."
        )
        self.footer.addSubview_(self.keep_original)

        self.progress = AK.NSProgressIndicator.alloc().initWithFrame_(AK.NSZeroRect)
        self.progress.setStyle_(AK.NSProgressIndicatorStyleBar)
        self.progress.setIndeterminate_(False)
        self.progress.setMinValue_(0)
        self.progress.setMaxValue_(100)
        self.progress.setDoubleValue_(0)
        self.progress.setHidden_(True)
        self.footer.addSubview_(self.progress)

        self.again_button = AK.NSButton.alloc().initWithFrame_(AK.NSZeroRect)
        self.again_button.setTitle_("Again")
        self.again_button.setBezelStyle_(AK.NSBezelStyleRounded)
        self.again_button.setControlSize_(AK.NSControlSizeSmall)
        self.again_button.setImage_(
            AK.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                "arrow.clockwise", "Repeat"
            )
        )
        self.again_button.setImagePosition_(AK.NSImageLeading)
        self.again_button.setEnabled_(False)
        self.again_button.setTarget_(self)
        self.again_button.setAction_("repeatLastBatch:")
        self.footer.addSubview_(self.again_button)

        self.quality_selector = AK.NSPopUpButton.alloc().initWithFrame_pullsDown_(
            AK.NSZeroRect, False
        )
        self.quality_selector.setControlSize_(AK.NSControlSizeSmall)
        self.quality_selector.addItemsWithTitles_(list(QUALITY_CONTROL_LABELS))
        self.quality_selector.setTarget_(self)
        self.quality_selector.setAction_("selectQuality:")
        self.footer.addSubview_(self.quality_selector)
        self._update_quality_menu()
        self.layout_controls()

    def layout_controls(self):
        bounds = self.canvas.bounds()
        width = bounds.size.width
        height = bounds.size.height
        footer_height = self.FOOTER_HEIGHT

        self.footer.setFrame_(AK.NSMakeRect(0, 0, width, footer_height))
        self.separator.setFrame_(AK.NSMakeRect(0, footer_height - 1, width, 1))
        self.results_scroll.setFrame_(AK.NSMakeRect(0, footer_height, width, height - footer_height))
        results_height = max(
            height - footer_height,
            self.results_table.requiredHeightForWidth_(width),
        )
        self.results_table.setFrame_(AK.NSMakeRect(0, 0, width, results_height))

        # Keep the 14 px outer inset, 28 px controls, and 8 px corners used by
        # the website preview so the native footer reads as one calm toolbar.
        control_y = (footer_height - 28) / 2
        self.add_button.setFrame_(AK.NSMakeRect(14, control_y, 34, 28))

        right = width - 14
        self.quality_selector.setFrame_(AK.NSMakeRect(right - 106, control_y, 106, 28))
        right -= 116
        self.again_button.setFrame_(AK.NSMakeRect(right - 80, control_y, 80, 28))
        right -= 90
        self.progress.setFrame_(
            AK.NSMakeRect(right - 132, (footer_height - 4) / 2, 132, 4)
        )
        self.keep_original.setFrame_(
            AK.NSMakeRect(right - 132, (footer_height - 24) / 2, 132, 24)
        )

        label_x = 58
        label_width = max(90, right - 142 - label_x)
        self.status_label.setFrame_(
            AK.NSMakeRect(label_x, (footer_height - 20) / 2, label_width, 20)
        )
        self.canvas.setNeedsDisplay_(True)

    def windowDidResize_(self, notification):
        self.layout_controls()

    def windowWillClose_(self, notification):
        AK.NSApp.terminate_(self)

    def handle_drop_urls(self, urls):
        paths = [str(url.path()) for url in urls if url.isFileURL()]
        self._start_paths(paths)

    def _expand_pdf_paths(self, paths):
        pdfs = []
        for raw_path in paths:
            path = Path(raw_path)
            if path.is_file() and path.suffix.lower() == ".pdf":
                pdfs.append(str(path))
            elif path.is_dir():
                pdfs.extend(
                    str(candidate)
                    for candidate in path.rglob("*")
                    if candidate.is_file() and candidate.suffix.lower() == ".pdf"
                )
        return list(dict.fromkeys(pdfs))

    def _start_paths(self, paths):
        if self.processing:
            self.status_label.setStringValue_("Wait for the current batch to finish")
            return
        pdfs = self._expand_pdf_paths(paths)
        if not pdfs:
            self.status_label.setStringValue_("Choose PDF files")
            return

        self.pdf_files = pdfs
        self.statuses = [Path(path).name for path in pdfs]
        self.metrics = [None] * len(pdfs)
        self._show_results()
        self._start_compression()

    def _show_results(self):
        self.showing_results = True
        table_height = self.results_table.requiredHeightForWidth_(680)
        target_height = min(460, max(190, table_height + self.FOOTER_HEIGHT + 12))
        self.window.setContentSize_(AK.NSMakeSize(680, target_height))
        self.results_scroll.setHidden_(False)
        self.layout_controls()
        self.results_table.setNeedsDisplay_(True)
        self.canvas.setNeedsDisplay_(True)

    def _start_compression(self):
        if self.processing or not self.pdf_files:
            return
        self.processing = True
        self.status_label.setStringValue_("Compressing PDFs…")
        self.add_button.setEnabled_(False)
        self.keep_original.setEnabled_(False)
        self.keep_original.setHidden_(True)
        self.again_button.setEnabled_(False)
        self.quality_selector.setEnabled_(False)
        self.progress.setDoubleValue_(0)
        self.progress.setHidden_(False)

        _, setting, _ = QUALITY_PROFILES[self.quality_index]
        keep_original = self.keep_original.state() == AK.NSControlStateValueOn
        worker = threading.Thread(
            target=self._compress_worker,
            args=(list(self.pdf_files), setting, keep_original),
            daemon=True,
        )
        worker.start()

    def _compress_worker(self, paths, setting, keep_original):
        total = len(paths)
        try:
            for index, path in enumerate(paths):
                status, metrics = compress_pdf(path, setting, keep_original)
                progress = (index + 1) / total * 100
                AppHelper.callAfter(self._update_result, index, status, metrics, progress)
        except Exception:
            compression_logger().exception("Unexpected batch worker failure")
        finally:
            AppHelper.callAfter(self._finish_compression)

    def _update_result(self, index, status, metrics, progress):
        self.statuses[index] = status
        self.metrics[index] = metrics
        self.results_table.setNeedsDisplay_(True)
        self.progress.setDoubleValue_(progress)

    def _finish_compression(self):
        self.processing = False
        completed = [metric for metric in self.metrics if metric]
        if completed:
            average = sum(
                metric["saved_size"] / metric["original_size"] * 100
                for metric in completed
            ) / len(completed)
            saved = sum(metric["saved_size"] for metric in completed)
            self.status_label.setStringValue_(
                f"Done — {average:.1f}% average · {format_file_size(saved)} saved"
            )
        else:
            self.status_label.setStringValue_("Done — no files were reduced")
        self.add_button.setEnabled_(True)
        self.keep_original.setEnabled_(True)
        self.keep_original.setHidden_(False)
        self.progress.setHidden_(True)
        self.again_button.setEnabled_(bool(self.pdf_files))
        self.quality_selector.setEnabled_(True)

    def _update_quality_menu(self):
        label, _, _ = QUALITY_PROFILES[self.quality_index]
        self.quality_selector.selectItemAtIndex_(self.quality_index)
        self.quality_selector.setToolTip_(f"Quality: {label}")

    def chooseFiles_(self, sender):
        panel = AK.NSOpenPanel.openPanel()
        panel.setCanChooseFiles_(True)
        panel.setCanChooseDirectories_(True)
        panel.setAllowsMultipleSelection_(True)
        panel.setAllowedFileTypes_(["pdf"])
        panel.setPrompt_("Compress")
        if panel.runModal() == AK.NSModalResponseOK:
            self._start_paths([str(url.path()) for url in panel.URLs()])

    def repeatLastBatch_(self, sender):
        if not self.processing and self.pdf_files:
            self.statuses = [Path(path).name for path in self.pdf_files]
            self.metrics = [None] * len(self.pdf_files)
            self.results_table.setNeedsDisplay_(True)
            self._start_compression()

    def selectQuality_(self, sender):
        self.quality_index = sender.indexOfSelectedItem()
        self._update_quality_menu()


class AppDelegate(FN.NSObject):
    def applicationDidFinishLaunching_(self, notification):
        self._build_main_menu()
        self.updater_controller = load_sparkle_updater()
        self.controller = PDFCompressorController.alloc().init()
        self.controller.window.makeKeyAndOrderFront_(None)
        AK.NSApp.activateIgnoringOtherApps_(True)

    def _build_main_menu(self):
        main_menu = AK.NSMenu.alloc().init()
        application_item = AK.NSMenuItem.alloc().init()
        main_menu.addItem_(application_item)

        application_menu = AK.NSMenu.alloc().initWithTitle_(APP_NAME)
        about_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"About {APP_NAME}", "showAbout:", ""
        )
        about_item.setTarget_(self)
        application_menu.addItem_(about_item)

        contribute_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Contribute to the project…", "openContribute:", ""
        )
        contribute_item.setTarget_(self)
        application_menu.addItem_(contribute_item)

        donate_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "♥ Support the project…", "openDonate:", ""
        )
        donate_item.setTarget_(self)
        application_menu.addItem_(donate_item)
        application_menu.addItem_(AK.NSMenuItem.separatorItem())

        update_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Check for Updates…", "checkForUpdates:", ""
        )
        update_item.setTarget_(self)
        application_menu.addItem_(update_item)
        application_menu.addItem_(AK.NSMenuItem.separatorItem())

        hide_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"Hide {APP_NAME}", "hide:", "h"
        )
        application_menu.addItem_(hide_item)
        application_menu.addItem_(AK.NSMenuItem.separatorItem())

        quit_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"Quit {APP_NAME}", "terminate:", "q"
        )
        application_menu.addItem_(quit_item)
        application_item.setSubmenu_(application_menu)
        AK.NSApp.setMainMenu_(main_menu)

    def showAbout_(self, sender):
        text = (
            "Fast and Simple PDF Compressor\n\n"
            "Created because compressing a PDF should be as simple as "
            "drag, drop, and done.\n\n"
            "Daniel Lares · July 22, 2026\n\n"
            "No warranty · GNU AGPL v3\n"
            "Source and contributions  ·  ♥ Support the project\n"
            "Ghostscript 10.07.1"
        )
        credits = FN.NSMutableAttributedString.alloc().initWithString_(text)
        full_range = FN.NSMakeRange(0, len(text))
        credits.addAttribute_value_range_(
            AK.NSFontAttributeName, AK.NSFont.systemFontOfSize_(11.5), full_range
        )
        credits.addAttribute_value_range_(
            AK.NSForegroundColorAttributeName,
            AK.NSColor.secondaryLabelColor(),
            full_range,
        )

        paragraph = AK.NSMutableParagraphStyle.alloc().init()
        paragraph.setAlignment_(AK.NSTextAlignmentCenter)
        paragraph.setLineSpacing_(2.0)
        credits.addAttribute_value_range_(
            AK.NSParagraphStyleAttributeName, paragraph, full_range
        )

        links = {
            "Source and contributions": REPOSITORY_URL,
            "♥ Support the project": DONATE_URL,
            "Ghostscript 10.07.1": "https://ghostscript.com/licensing/",
            "GNU AGPL v3": "https://www.gnu.org/licenses/agpl-3.0.html",
        }
        for label, url in links.items():
            start = text.index(label)
            link_range = FN.NSMakeRange(start, len(label))
            credits.addAttribute_value_range_(
                AK.NSLinkAttributeName, FN.NSURL.URLWithString_(url), link_range
            )
            credits.addAttribute_value_range_(
                AK.NSForegroundColorAttributeName, AK.NSColor.linkColor(), link_range
            )

        AK.NSApp.orderFrontStandardAboutPanelWithOptions_(
            {
                AK.NSAboutPanelOptionApplicationName: APP_NAME,
                AK.NSAboutPanelOptionApplicationVersion: APP_VERSION,
                AK.NSAboutPanelOptionVersion: "",
                AK.NSAboutPanelOptionCredits: credits,
            }
        )

    def openContribute_(self, sender):
        AK.NSWorkspace.sharedWorkspace().openURL_(
            FN.NSURL.URLWithString_(CONTRIBUTE_URL)
        )

    def openDonate_(self, sender):
        AK.NSWorkspace.sharedWorkspace().openURL_(
            FN.NSURL.URLWithString_(DONATE_URL)
        )

    def checkForUpdates_(self, sender):
        if self.updater_controller is None:
            alert = AK.NSAlert.alloc().init()
            alert.setMessageText_("Updates are unavailable")
            alert.setInformativeText_(
                "The bundled updater could not be loaded. Download the latest version "
                "from the FS PDF Compressor website."
            )
            alert.runModal()
            return
        self.updater_controller.checkForUpdates_(sender)

    def applicationShouldTerminateAfterLastWindowClosed_(self, application):
        return True


def main():
    application = AK.NSApplication.sharedApplication()
    application.setActivationPolicy_(AK.NSApplicationActivationPolicyRegular)
    delegate = AppDelegate.alloc().init()
    application.setDelegate_(delegate)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
