import os
import re
import sys
import errno
import ctypes
import subprocess


def discores_osx():
    """Use AppKit, that may not be installed with this interpreter"""
    try:
        import AppKit
        size = AppKit.NSScreen.mainScreen().frame().size
        return int(size.width), int(size.height)
    except ImportError:
        pass

    # If AppKit not in this python interpreter, try to use the system one
    script = """
        import AppKit
        size = AppKit.NSScreen.mainScreen().frame().size
        print("%d %d" % (size.width, size.height))
    """

    script = script.strip().replace('\n', ';')

    run = ['/usr/bin/python',  '-c', script]

    output = subprocess.check_output(run)
    return tuple(map(int, output.strip().split(' ')))


def discores_x():
    check = re.compile(r'\s+(\d+)x(\d+)\s+[.0-9]+\*')
    output = subprocess.check_output(['xrandr'])
    for line in output.split('\n'):
        match = check.match(line)
        if match:
            return int(match.group(1)), int(match.group(2))

    return None


def discores_win32():
    user32 = ctypes.windll.user32

    width = user32.GetSystemMetrics(0x0)
    height = user32.GetSystemMetrics(0x1)

    return width, height


def discores():
    if sys.platform == 'darwin':
        return discores_osx()
    if sys.platform in ('win32', 'cygwin'):
        return discores_win32()

    return discores_x()


if __name__ == '__main__':
    print('Width: %s - Height: %s' % discores())