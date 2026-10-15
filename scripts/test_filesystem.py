"""Filesystem fixtures used by the product acceptance suites."""

import os
import time


def cleanup_temporary_directory(directory):
    """Wait briefly for pending Windows deletions; persistent cleanup errors fail."""
    for attempt in range(6):
        try:
            directory.cleanup()
            return
        except OSError as error:
            if os.name != "nt" or getattr(error, "winerror", None) not in {32, 145} or attempt == 5:
                raise
            time.sleep(0.02 * 2**attempt)


def sparse_truncate(handle, size):
    """Keep the real logical size without allocating terabytes on Windows."""
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        control = kernel.DeviceIoControl
        control.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                            wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                            wintypes.LPVOID]
        control.restype = wintypes.BOOL
        seek = kernel.SetFilePointerEx
        seek.argtypes = [wintypes.HANDLE, ctypes.c_longlong, wintypes.LPVOID, wintypes.DWORD]
        seek.restype = wintypes.BOOL
        end = kernel.SetEndOfFile
        end.argtypes = [wintypes.HANDLE]
        end.restype = wintypes.BOOL
        handle.flush()
        position = handle.tell()
        native = msvcrt.get_osfhandle(handle.fileno())
        returned = wintypes.DWORD()
        if not control(native, 0x900C4, None, 0, None, 0, ctypes.byref(returned), None):
            raise ctypes.WinError(ctypes.get_last_error())
        # Avoid CRT resize helpers that may write zeroes across the extended range.
        if not seek(native, size, None, 0) or not end(native):
            raise ctypes.WinError(ctypes.get_last_error())
        handle.seek(position)
    else:
        handle.truncate(size)
    handle.flush()
    assert os.fstat(handle.fileno()).st_size == size
