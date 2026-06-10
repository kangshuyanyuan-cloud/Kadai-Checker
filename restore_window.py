import ctypes
import sys

def restore_moodle_window():
    user32 = ctypes.windll.user32
    
    # ウィンドウを列挙するコールバック関数
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
    
    target_hwnd = None
    
    def enum_windows_proc(hwnd, lParam):
        nonlocal target_hwnd
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            # タイトルに "Moodle課題チェッカー" が含まれるウィンドウを探す
            if "Moodle課題チェッカー" in buff.value:
                target_hwnd = hwnd
                return False  # 見つかったら列挙終了
        return True
    
    user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)
    
    if target_hwnd:
        # ウィンドウを元に戻して最前面へ (SW_RESTORE = 9)
        user32.ShowWindow(target_hwnd, 9)
        user32.SetForegroundWindow(target_hwnd)

if __name__ == "__main__":
    restore_moodle_window()
