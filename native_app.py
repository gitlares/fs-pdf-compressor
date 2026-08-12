# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

import os
import threading
from pathlib import Path

import AppKit as AK
import Foundation as FN
import objc
from PyObjCTools import AppHelper

from fs_pdf_compressor.batch import BatchSummary, completion_text
from fs_pdf_compressor.core import (
    QUALITY_PROFILES,
    bundle_contents_dir,
    compress_pdf,
    compression_logger,
    expand_pdf_paths,
)
from fs_pdf_compressor.macos_drop_zone import DropZonePanel
from fs_pdf_compressor.macos_login_item import (
    current_state as login_item_state,
    open_login_items_settings,
    set_enabled as set_login_item_enabled,
)
from fs_pdf_compressor.macos_views import DropCanvas, ResultsTableView


APP_NAME = "FS PDF Compressor"
APP_VERSION = os.environ.get("APP_VERSION", "1.0.11")
REPOSITORY_URL = "https://github.com/gitlares/fs-pdf-compressor"
CONTRIBUTE_URL = f"{REPOSITORY_URL}/blob/main/CONTRIBUTING.md"
DONATE_URL = "https://www.paypal.com/donate/?hosted_button_id=7RDCBR3QXXEMJ"
DROP_ZONE_DEFAULTS_KEY = "DropZoneEnabled"


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


class PDFCompressorController(FN.NSObject):
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
        self._batch_from_drop_zone = False
        self.drop_zone = None
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
        self.window.setReleasedWhenClosed_(False)
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
        self.add_button.setControlSize_(AK.NSControlSizeRegular)
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
        self.again_button.setControlSize_(AK.NSControlSizeRegular)
        self.again_button.setFont_(AK.NSFont.systemFontOfSize_(12.0))
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

        self.options_button = AK.NSButton.alloc().initWithFrame_(AK.NSZeroRect)
        self.options_button.setBezelStyle_(AK.NSBezelStyleRounded)
        self.options_button.setControlSize_(AK.NSControlSizeRegular)
        self.options_button.setImage_(
            AK.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                "ellipsis", "Options"
            )
        )
        self.options_button.setImagePosition_(AK.NSImageOnly)
        self.options_button.setTarget_(self)
        self.options_button.setAction_("showOptions:")
        self.footer.addSubview_(self.options_button)

        self.quality_menu = AK.NSMenu.alloc().initWithTitle_("Quality")
        self.quality_items = []
        for index, (label, _, description) in enumerate(QUALITY_PROFILES):
            item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                label, "selectQuality:", ""
            )
            item.setTarget_(self)
            item.setTag_(index)
            item.setToolTip_(description)
            self.quality_menu.addItem_(item)
            self.quality_items.append(item)
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

        # Match the footer metrics used by the website preview.
        control_y = (footer_height - 28) / 2
        self.add_button.setFrame_(AK.NSMakeRect(14, control_y, 34, 28))

        right = width - 14
        self.options_button.setFrame_(AK.NSMakeRect(right - 34, control_y, 34, 28))
        right -= 42
        self.again_button.setFrame_(AK.NSMakeRect(right - 88, control_y, 88, 28))
        right -= 98
        self.progress.setFrame_(
            AK.NSMakeRect(right - 132, (footer_height - 4) / 2, 132, 4)
        )
        keep_width = 96
        self.keep_original.setFrame_(
            AK.NSMakeRect(right - keep_width, (footer_height - 24) / 2, keep_width, 24)
        )

        label_x = 58
        label_width = max(90, right - keep_width - 10 - label_x)
        # NSTextField's label baseline sits slightly higher than regular
        # NSButton content. Lower the frame by two points so the visible text,
        # checkbox label, and button titles share one optical baseline.
        label_y = (footer_height - 20) / 2 - 2
        self.status_label.setFrame_(
            AK.NSMakeRect(label_x, label_y, label_width, 20)
        )
        self.canvas.setNeedsDisplay_(True)

    def windowDidResize_(self, notification):
        self.layout_controls()

    def handle_drop_urls(self, urls):
        paths = [str(url.path()) for url in urls if url.isFileURL()]
        self._start_paths(paths)

    def _expand_pdf_paths(self, paths):
        return expand_pdf_paths(paths)

    def _start_paths(self, paths, from_drop_zone=False):
        if self.processing:
            self.status_label.setStringValue_("Wait for the current batch to finish")
            return False
        pdfs = self._expand_pdf_paths(paths)
        if not pdfs:
            self.status_label.setStringValue_("Choose PDF files")
            return False

        self._batch_from_drop_zone = from_drop_zone
        self.pdf_files = pdfs
        self.statuses = [Path(path).name for path in pdfs]
        self.metrics = [None] * len(pdfs)
        self._show_results()
        self._start_compression()
        return True

    def start_drop_zone_paths(self, paths):
        return self._start_paths(paths, from_drop_zone=True)

    def show_main_window(self):
        self.window.makeKeyAndOrderFront_(None)
        AK.NSApp.activateIgnoringOtherApps_(True)

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
        self.options_button.setEnabled_(False)
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
        if self._batch_from_drop_zone and self.drop_zone is not None:
            self.drop_zone.batch_progress(index + 1, len(self.pdf_files))

    def _finish_compression(self):
        self.processing = False
        summary = BatchSummary.from_metrics(self.metrics)
        self.status_label.setStringValue_(completion_text(self.metrics))
        self.add_button.setEnabled_(True)
        self.keep_original.setEnabled_(True)
        self.keep_original.setHidden_(False)
        self.progress.setHidden_(True)
        self.again_button.setEnabled_(bool(self.pdf_files))
        self.options_button.setEnabled_(True)
        if self._batch_from_drop_zone and self.drop_zone is not None:
            self.drop_zone.batch_finished(summary)
        self._batch_from_drop_zone = False

    def _update_quality_menu(self):
        for index, item in enumerate(self.quality_items):
            item.setState_(
                AK.NSControlStateValueOn
                if index == self.quality_index
                else AK.NSControlStateValueOff
            )
        label, _, _ = QUALITY_PROFILES[self.quality_index]
        self.options_button.setToolTip_(f"Quality: {label}")

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

    def showOptions_(self, sender):
        location = AK.NSMakePoint(0, sender.bounds().size.height + 3)
        self.quality_menu.popUpMenuPositioningItem_atLocation_inView_(
            None, location, sender
        )

    def selectQuality_(self, sender):
        self.quality_index = sender.tag()
        self._update_quality_menu()


class AppDelegate(FN.NSObject):
    def applicationDidFinishLaunching_(self, notification):
        self.drop_zone_panel = None
        self._build_main_menu()
        self.updater_controller = load_sparkle_updater()
        self.controller = PDFCompressorController.alloc().init()
        if FN.NSUserDefaults.standardUserDefaults().boolForKey_(
            DROP_ZONE_DEFAULTS_KEY
        ):
            self._set_drop_zone_enabled(True)
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

        self.drop_zone_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Show Drop Zone", "toggleDropZone:", ""
        )
        self.drop_zone_item.setTarget_(self)
        self.drop_zone_item.setState_(
            AK.NSControlStateValueOn
            if FN.NSUserDefaults.standardUserDefaults().boolForKey_(
                DROP_ZONE_DEFAULTS_KEY
            )
            else AK.NSControlStateValueOff
        )
        application_menu.addItem_(self.drop_zone_item)

        self.launch_at_login_item = (
            AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Launch at Login", "toggleLaunchAtLogin:", ""
            )
        )
        self.launch_at_login_item.setTarget_(self)
        self._refresh_launch_at_login_item()
        application_menu.addItem_(self.launch_at_login_item)
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

    def toggleDropZone_(self, sender):
        enabled = sender.state() != AK.NSControlStateValueOn
        self._set_drop_zone_enabled(enabled)
        FN.NSUserDefaults.standardUserDefaults().setBool_forKey_(
            enabled, DROP_ZONE_DEFAULTS_KEY
        )

    def toggleLaunchAtLogin_(self, sender):
        enabled = not login_item_state().enabled
        success, error = set_login_item_enabled(enabled)
        self._refresh_launch_at_login_item()
        if not success:
            alert = AK.NSAlert.alloc().init()
            alert.setMessageText_("Could not change Launch at Login")
            alert.setInformativeText_(error or "macOS rejected the change.")
            alert.runModal()
            return
        if login_item_state().requires_approval:
            alert = AK.NSAlert.alloc().init()
            alert.setMessageText_("Approve Launch at Login")
            alert.setInformativeText_(
                "macOS requires your approval in System Settings before "
                "FS PDF Compressor can open automatically."
            )
            alert.addButtonWithTitle_("Open System Settings")
            alert.addButtonWithTitle_("Later")
            if alert.runModal() == AK.NSAlertFirstButtonReturn:
                open_login_items_settings()

    def _refresh_launch_at_login_item(self):
        state = login_item_state()
        self.launch_at_login_item.setState_(
            AK.NSControlStateValueOn
            if state.enabled
            else AK.NSControlStateValueOff
        )

    def _set_drop_zone_enabled(self, enabled):
        self.drop_zone_item.setState_(
            AK.NSControlStateValueOn
            if enabled
            else AK.NSControlStateValueOff
        )
        if enabled:
            if self.drop_zone_panel is None:
                self.drop_zone_panel = DropZonePanel.alloc().initWithController_(
                    self.controller
                )
            self.controller.drop_zone = self.drop_zone_panel
            self.drop_zone_panel.show_panel()
            return

        self.controller.drop_zone = None
        if self.drop_zone_panel is not None:
            self.drop_zone_panel.orderOut_(None)
        if not self.controller.window.isVisible():
            self.controller.show_main_window()

    def applicationShouldTerminateAfterLastWindowClosed_(self, application):
        return not FN.NSUserDefaults.standardUserDefaults().boolForKey_(
            DROP_ZONE_DEFAULTS_KEY
        )


def main():
    application = AK.NSApplication.sharedApplication()
    application.setActivationPolicy_(AK.NSApplicationActivationPolicyRegular)
    delegate = AppDelegate.alloc().init()
    application.setDelegate_(delegate)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
