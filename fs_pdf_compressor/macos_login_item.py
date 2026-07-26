# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Daniel Lares

"""Native macOS launch-at-login support."""

from __future__ import annotations

from dataclasses import dataclass

import ServiceManagement as SM


@dataclass(frozen=True)
class LoginItemState:
    enabled: bool
    requires_approval: bool = False


def current_state() -> LoginItemState:
    status = SM.SMAppService.mainAppService().status()
    return LoginItemState(
        enabled=status
        in (SM.SMAppServiceStatusEnabled, SM.SMAppServiceStatusRequiresApproval),
        requires_approval=status == SM.SMAppServiceStatusRequiresApproval,
    )


def set_enabled(enabled: bool) -> tuple[bool, str | None]:
    service = SM.SMAppService.mainAppService()
    selector = (
        service.registerAndReturnError_
        if enabled
        else service.unregisterAndReturnError_
    )
    try:
        result = selector(None)
    except Exception as error:
        return False, str(error)

    # Objective-C's BOOL + NSError** is returned as (success, error) by PyObjC.
    if isinstance(result, tuple):
        success, error = result
    else:
        success, error = bool(result), None
    if success:
        return True, None
    if error is None:
        return False, "macOS did not accept the login item change."
    try:
        return False, str(error.localizedDescription())
    except Exception:
        return False, str(error)


def open_login_items_settings() -> None:
    SM.SMAppService.openSystemSettingsLoginItems()
