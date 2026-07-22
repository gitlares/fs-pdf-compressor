# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

import glob
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
APP_VERSION = "1.0.0"
REPOSITORY_URL = "https://github.com/gitlares/fs-pdf-compressor"
CONTRIBUTE_URL = f"{REPOSITORY_URL}/blob/main/CONTRIBUTING.md"


QUALITY_PROFILES = [
    (
        "Conservar calidad (mínima pérdida)",
        "/prepress",
        "Conserva resolución y calidad para impresión; el archivo puede reducir poco.",
    ),
    (
        "Equilibrado (recomendado)",
        "/ebook",
        "Reduce el tamaño manteniendo una buena calidad en pantalla.",
    ),
    (
        "Máxima compresión",
        "/screen",
        "Reduce más el archivo, con una pérdida visual mayor.",
    ),
]


def get_file_size_kb(path):
    return os.path.getsize(path) / 1024


def compressed_copy_path(original_path):
    path = Path(original_path)
    candidate = path.with_name(f"{path.stem} comprimido{path.suffix}")
    sequence = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} comprimido {sequence}{path.suffix}")
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
    gs_path, gs_environment = get_ghostscript_config()
    if not gs_path:
        return f"{os.path.basename(original_path)} — Ghostscript no disponible"

    original_size = get_file_size_kb(original_path)
    temp_path = original_path + ".temp.pdf"
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
        return f"{os.path.basename(original_path)} — no se pudo comprimir"

    new_size = get_file_size_kb(temp_path)
    if new_size >= original_size:
        os.unlink(temp_path)
        return f"{os.path.basename(original_path)} — sin cambio"

    output_path = compressed_copy_path(original_path) if keep_original else original_path
    os.replace(temp_path, output_path)
    reduction = 100 - (new_size / original_size * 100)
    return f"{os.path.basename(output_path)}   ↓ {reduction:.1f}%"


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


class PDFCompressorController(FN.NSObject):
    FOOTER_HEIGHT = 50.0

    def init(self):
        self = objc.super(PDFCompressorController, self).init()
        if self is None:
            return None
        self.pdf_files = []
        self.statuses = []
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
        self.results_scroll.setDrawsBackground_(False)
        self.results_scroll.setHidden_(True)
        self.results_text = AK.NSTextView.alloc().initWithFrame_(AK.NSZeroRect)
        self.results_text.setEditable_(False)
        self.results_text.setSelectable_(True)
        self.results_text.setRichText_(False)
        self.results_text.setDrawsBackground_(False)
        self.results_text.setFont_(AK.NSFont.systemFontOfSize_(13.0))
        self.results_text.setTextContainerInset_(AK.NSMakeSize(22, 20))
        self.results_scroll.setDocumentView_(self.results_text)
        self.canvas.addSubview_(self.results_scroll)

        self.footer = AK.NSVisualEffectView.alloc().initWithFrame_(AK.NSZeroRect)
        self.footer.setMaterial_(AK.NSVisualEffectMaterialHeaderView)
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
            AK.NSImage.imageWithSystemSymbolName_accessibilityDescription_("plus", "Añadir")
        )
        self.add_button.setImagePosition_(AK.NSImageOnly)
        self.add_button.setToolTip_("Elegir archivos PDF")
        self.add_button.setTarget_(self)
        self.add_button.setAction_("chooseFiles:")
        self.footer.addSubview_(self.add_button)

        self.status_label = AK.NSTextField.labelWithString_("Arrastra PDFs al área superior")
        self.status_label.setFont_(AK.NSFont.systemFontOfSize_(13.0))
        self.status_label.setLineBreakMode_(AK.NSLineBreakByTruncatingTail)
        self.footer.addSubview_(self.status_label)

        self.keep_original = AK.NSButton.checkboxWithTitle_target_action_(
            "Conservar original", self, None
        )
        self.keep_original.setControlSize_(AK.NSControlSizeSmall)
        self.keep_original.setToolTip_(
            "Guarda “nombre comprimido.pdf” sin modificar el PDF original."
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
        self.again_button.setTitle_("Otra vez")
        self.again_button.setBezelStyle_(AK.NSBezelStyleRounded)
        self.again_button.setControlSize_(AK.NSControlSizeSmall)
        self.again_button.setImage_(
            AK.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                "arrow.clockwise", "Repetir"
            )
        )
        self.again_button.setImagePosition_(AK.NSImageLeading)
        self.again_button.setEnabled_(False)
        self.again_button.setTarget_(self)
        self.again_button.setAction_("repeatLastBatch:")
        self.footer.addSubview_(self.again_button)

        self.options_button = AK.NSButton.alloc().initWithFrame_(AK.NSZeroRect)
        self.options_button.setBezelStyle_(AK.NSBezelStyleRounded)
        self.options_button.setControlSize_(AK.NSControlSizeSmall)
        self.options_button.setImage_(
            AK.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
                "ellipsis.circle", "Opciones"
            )
        )
        self.options_button.setImagePosition_(AK.NSImageOnly)
        self.options_button.setTarget_(self)
        self.options_button.setAction_("showOptions:")
        self.footer.addSubview_(self.options_button)

        self.quality_menu = AK.NSMenu.alloc().initWithTitle_("Calidad")
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

        control_y = (footer_height - 28) / 2
        self.add_button.setFrame_(AK.NSMakeRect(14, control_y, 34, 28))

        right = width - 14
        self.options_button.setFrame_(AK.NSMakeRect(right - 34, control_y, 34, 28))
        right -= 42
        self.again_button.setFrame_(AK.NSMakeRect(right - 88, control_y, 88, 28))
        right -= 98
        self.progress.setFrame_(
            AK.NSMakeRect(right - 72, (footer_height - 4) / 2, 72, 4)
        )
        right -= 82
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
            self.status_label.setStringValue_("Espera a que termine el lote actual")
            return
        pdfs = self._expand_pdf_paths(paths)
        if not pdfs:
            self.status_label.setStringValue_("Selecciona archivos PDF")
            return

        self.pdf_files = pdfs
        self.statuses = [Path(path).name for path in pdfs]
        self._show_results()
        self._start_compression()

    def _show_results(self):
        self.showing_results = True
        self.results_text.setString_("\n".join(self.statuses))
        self.results_scroll.setHidden_(False)
        self.canvas.setNeedsDisplay_(True)

    def _start_compression(self):
        if self.processing or not self.pdf_files:
            return
        self.processing = True
        self.status_label.setStringValue_("Comprimiendo PDFs…")
        self.add_button.setEnabled_(False)
        self.keep_original.setEnabled_(False)
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
        for index, path in enumerate(paths):
            status = compress_pdf(path, setting, keep_original)
            progress = (index + 1) / total * 100
            AppHelper.callAfter(self._update_result, index, status, progress)
        AppHelper.callAfter(self._finish_compression)

    def _update_result(self, index, status, progress):
        self.statuses[index] = status
        self.results_text.setString_("\n".join(self.statuses))
        self.progress.setDoubleValue_(progress)

    def _finish_compression(self):
        self.processing = False
        self.status_label.setStringValue_("Listo — arrastra más PDFs")
        self.add_button.setEnabled_(True)
        self.keep_original.setEnabled_(True)
        self.again_button.setEnabled_(bool(self.pdf_files))
        self.options_button.setEnabled_(True)

    def _update_quality_menu(self):
        for index, item in enumerate(self.quality_items):
            item.setState_(
                AK.NSControlStateValueOn
                if index == self.quality_index
                else AK.NSControlStateValueOff
            )
        label, _, _ = QUALITY_PROFILES[self.quality_index]
        self.options_button.setToolTip_(f"Calidad: {label}")

    def chooseFiles_(self, sender):
        panel = AK.NSOpenPanel.openPanel()
        panel.setCanChooseFiles_(True)
        panel.setCanChooseDirectories_(True)
        panel.setAllowsMultipleSelection_(True)
        panel.setAllowedFileTypes_(["pdf"])
        panel.setPrompt_("Comprimir")
        if panel.runModal() == AK.NSModalResponseOK:
            self._start_paths([str(url.path()) for url in panel.URLs()])

    def repeatLastBatch_(self, sender):
        if not self.processing and self.pdf_files:
            self.statuses = [Path(path).name for path in self.pdf_files]
            self.results_text.setString_("\n".join(self.statuses))
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
        self._build_main_menu()
        self.controller = PDFCompressorController.alloc().init()
        self.controller.window.makeKeyAndOrderFront_(None)
        AK.NSApp.activateIgnoringOtherApps_(True)

    def _build_main_menu(self):
        main_menu = AK.NSMenu.alloc().init()
        application_item = AK.NSMenuItem.alloc().init()
        main_menu.addItem_(application_item)

        application_menu = AK.NSMenu.alloc().initWithTitle_(APP_NAME)
        about_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"Acerca de {APP_NAME}", "showAbout:", ""
        )
        about_item.setTarget_(self)
        application_menu.addItem_(about_item)

        contribute_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Contribuir al proyecto…", "openContribute:", ""
        )
        contribute_item.setTarget_(self)
        application_menu.addItem_(contribute_item)
        application_menu.addItem_(AK.NSMenuItem.separatorItem())

        hide_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"Ocultar {APP_NAME}", "hide:", "h"
        )
        application_menu.addItem_(hide_item)
        application_menu.addItem_(AK.NSMenuItem.separatorItem())

        quit_item = AK.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"Salir de {APP_NAME}", "terminate:", "q"
        )
        application_menu.addItem_(quit_item)
        application_item.setSubmenu_(application_menu)
        AK.NSApp.setMainMenu_(main_menu)

    def showAbout_(self, sender):
        text = (
            "Fast and Simple PDF Compressor\n\n"
            "Creado porque comprimir un PDF debería ser tan simple como "
            "arrastrar, soltar y listo.\n\n"
            "Daniel Lares · 22 de julio de 2026\n\n"
            "Sin garantía · GNU AGPL v3\n"
            "Código y contribuciones  ·  Ghostscript 10.07.1"
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
            "Código y contribuciones": REPOSITORY_URL,
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
