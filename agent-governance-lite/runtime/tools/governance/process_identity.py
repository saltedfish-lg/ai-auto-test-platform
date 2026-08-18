from __future__ import annotations

import errno
import os
from dataclasses import dataclass
from typing import Final

RUNNING_MATCH: Final = 'RUNNING_MATCH'
RUNNING_UNVERIFIED: Final = 'RUNNING_UNVERIFIED'
NOT_RUNNING: Final = 'NOT_RUNNING'
PID_REUSED: Final = 'PID_REUSED'
ACCESS_DENIED: Final = 'ACCESS_DENIED'
IDENTITY_UNAVAILABLE: Final = 'IDENTITY_UNAVAILABLE'
INVALID_PID: Final = 'INVALID_PID'


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    creation_time: str | None


@dataclass(frozen=True)
class ProcessInspection:
    pid: int
    status: str
    creation_time: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class _ProcessSnapshot:
    pid: int
    running: bool | None
    creation_time: str | None = None
    status: str | None = None
    detail: str | None = None


def _linux_creation_identity(pid: int) -> str | None:
    """Return Linux /proc start ticks without introducing a third-party dependency."""
    if not sys_platform_is_linux():
        return None
    try:
        raw = open(f'/proc/{pid}/stat', 'r', encoding='utf-8').read()
        close = raw.rfind(')')
        if close < 0:
            return None
        fields = raw[close + 2:].split()
        # Field 22 is starttime. After removing pid/comm, field 3 is index 0.
        start_ticks = fields[19]
        return f'linux-startticks:{int(start_ticks)}'
    except (OSError, ValueError, IndexError):
        return None


def sys_platform_is_linux() -> bool:
    import sys
    return sys.platform.startswith('linux')


def _posix_process_snapshot(pid: int) -> _ProcessSnapshot:
    """Use the POSIX signal-0 convention only on non-Windows platforms."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return _ProcessSnapshot(pid, False, status=NOT_RUNNING)
    except PermissionError:
        return _ProcessSnapshot(pid, None, status=ACCESS_DENIED, detail='EPERM')
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return _ProcessSnapshot(pid, False, status=NOT_RUNNING)
        if exc.errno == errno.EPERM:
            return _ProcessSnapshot(pid, None, status=ACCESS_DENIED, detail='EPERM')
        return _ProcessSnapshot(pid, None, status=IDENTITY_UNAVAILABLE, detail=type(exc).__name__)
    return _ProcessSnapshot(pid, True, creation_time=_linux_creation_identity(pid))


def _windows_process_snapshot(pid: int) -> _ProcessSnapshot:
    """Read Windows process state/creation identity without sending a signal.

    The requested access rights are query/synchronization only. In particular, this
    function never requests PROCESS_TERMINATE and never calls os.kill/TerminateProcess.
    """
    import ctypes
    from ctypes import wintypes

    SYNCHRONIZE = 0x00100000
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    WAIT_OBJECT_0 = 0x00000000
    WAIT_TIMEOUT = 0x00000102
    WAIT_FAILED = 0xFFFFFFFF
    ERROR_ACCESS_DENIED = 5
    ERROR_INVALID_PARAMETER = 87

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_process.restype = wintypes.HANDLE
    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    wait_for_single_object.restype = wintypes.DWORD
    get_process_times = kernel32.GetProcessTimes
    get_process_times.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    get_process_times.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    handle = open_process(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error == ERROR_ACCESS_DENIED:
            return _ProcessSnapshot(pid, None, status=ACCESS_DENIED, detail=f'winerror={error}')
        if error == ERROR_INVALID_PARAMETER:
            return _ProcessSnapshot(pid, False, status=NOT_RUNNING, detail=f'winerror={error}')
        return _ProcessSnapshot(pid, None, status=IDENTITY_UNAVAILABLE, detail=f'winerror={error}')

    try:
        wait = int(wait_for_single_object(handle, 0))
        if wait == WAIT_OBJECT_0:
            return _ProcessSnapshot(pid, False, status=NOT_RUNNING)
        if wait == WAIT_FAILED:
            error = ctypes.get_last_error()
            return _ProcessSnapshot(pid, None, status=IDENTITY_UNAVAILABLE, detail=f'wait_winerror={error}')
        if wait != WAIT_TIMEOUT:
            return _ProcessSnapshot(pid, None, status=IDENTITY_UNAVAILABLE, detail=f'wait_status={wait}')

        created = wintypes.FILETIME()
        exited = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        if not get_process_times(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
            error = ctypes.get_last_error()
            return _ProcessSnapshot(pid, True, status=IDENTITY_UNAVAILABLE, detail=f'times_winerror={error}')
        creation_value = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
        return _ProcessSnapshot(pid, True, creation_time=f'win-filetime:{creation_value}')
    finally:
        close_handle(handle)


def _platform_process_snapshot(pid: int) -> _ProcessSnapshot:
    if os.name == 'nt':
        return _windows_process_snapshot(pid)
    return _posix_process_snapshot(pid)


def inspect_process(pid: int, expected_creation_time: str | None = None) -> ProcessInspection:
    """Inspect process liveness and, when supplied, verify owner creation identity."""
    try:
        normalized_pid = int(pid)
    except (TypeError, ValueError):
        return ProcessInspection(-1, INVALID_PID)
    if normalized_pid <= 0:
        return ProcessInspection(normalized_pid, INVALID_PID)

    snapshot = _platform_process_snapshot(normalized_pid)
    if snapshot.status in {NOT_RUNNING, ACCESS_DENIED, IDENTITY_UNAVAILABLE} and snapshot.running is not True:
        return ProcessInspection(normalized_pid, snapshot.status or IDENTITY_UNAVAILABLE, snapshot.creation_time, snapshot.detail)
    if snapshot.running is False:
        return ProcessInspection(normalized_pid, NOT_RUNNING, snapshot.creation_time, snapshot.detail)
    if snapshot.running is not True:
        return ProcessInspection(normalized_pid, snapshot.status or IDENTITY_UNAVAILABLE, snapshot.creation_time, snapshot.detail)

    if expected_creation_time:
        if not snapshot.creation_time:
            return ProcessInspection(normalized_pid, IDENTITY_UNAVAILABLE, None, snapshot.detail)
        if snapshot.creation_time != str(expected_creation_time):
            return ProcessInspection(normalized_pid, PID_REUSED, snapshot.creation_time)
        return ProcessInspection(normalized_pid, RUNNING_MATCH, snapshot.creation_time)
    return ProcessInspection(normalized_pid, RUNNING_UNVERIFIED, snapshot.creation_time)


def current_process_identity(pid: int | None = None) -> ProcessIdentity:
    """Capture the current identity available for a PID without changing process state."""
    normalized_pid = int(os.getpid() if pid is None else pid)
    inspection = inspect_process(normalized_pid)
    creation_time = inspection.creation_time if inspection.status in {RUNNING_MATCH, RUNNING_UNVERIFIED} else None
    return ProcessIdentity(normalized_pid, creation_time)


def owner_is_mechanically_stale(pid: int, expected_creation_time: str | None = None) -> tuple[bool, ProcessInspection]:
    """Return stale only when death or PID reuse is mechanically established.

    ACCESS_DENIED/IDENTITY_UNAVAILABLE/RUNNING_UNVERIFIED are conservative: callers
    must not delete a lock merely because identity could not be proven.
    """
    inspection = inspect_process(pid, expected_creation_time)
    return inspection.status in {NOT_RUNNING, PID_REUSED}, inspection
