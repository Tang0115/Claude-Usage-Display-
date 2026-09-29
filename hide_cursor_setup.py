#!/usr/bin/env python3
"""One-time setup: makes the desktop's mouse cursor invisible for the kiosk.

Why: on boot, the pointer you see is drawn by the Wayland compositor
(labwc), not Chromium. Chromium's `cursor: none` only takes over once the
compositor sends it a pointer-enter event, which needs a real mouse move —
synthetic events injected into Chromium (e.g. over DevTools) never reach
the compositor, so they can't hide it.

Fix: install a cursor theme where every cursor is a transparent 1x1 image,
and point labwc at it via ~/.config/labwc/environment (user settings
override /etc/xdg/labwc/environment's XCURSOR_THEME=PiXtrix). Takes effect
on the next login/reboot. Safe to re-run.

To undo: delete the XCURSOR_THEME line from ~/.config/labwc/environment
and reboot.
"""
import os
import struct

THEME = 'clawd-hidden'
THEME_DIR = os.path.expanduser(f'~/.icons/{THEME}')
LABWC_ENV = os.path.expanduser('~/.config/labwc/environment')
# Cursor names come from the installed themes so every shape (arrow, text,
# resize, busy, ...) resolves to the blank one rather than a visible fallback.
SOURCE_THEMES = ['/usr/share/icons/PiXtrix/cursors', '/usr/share/icons/Adwaita/cursors']
NOMINAL_SIZE = 24


def blank_xcursor():
    """A valid Xcursor file with a single fully transparent 1x1 image."""
    image_type = 0xfffd0002
    header = struct.pack('<4sIII', b'Xcur', 16, 0x10000, 1)
    toc = struct.pack('<III', image_type, NOMINAL_SIZE, 16 + 12)
    image = struct.pack('<IIIIIIIII', 36, image_type, NOMINAL_SIZE, 1,
                        1, 1, 0, 0, 0)  # width, height, xhot, yhot, delay
    pixel = struct.pack('<I', 0)  # ARGB, alpha 0
    return header + toc + image + pixel


def main():
    cursors_dir = os.path.join(THEME_DIR, 'cursors')
    os.makedirs(cursors_dir, exist_ok=True)

    blank_path = os.path.join(cursors_dir, 'default')
    with open(blank_path, 'wb') as f:
        f.write(blank_xcursor())

    names = {'left_ptr'}
    for src in SOURCE_THEMES:
        if os.path.isdir(src):
            names.update(os.listdir(src))
    names.discard('default')
    for name in sorted(names):
        link = os.path.join(cursors_dir, name)
        if os.path.lexists(link):
            os.remove(link)
        os.symlink('default', link)

    with open(os.path.join(THEME_DIR, 'index.theme'), 'w') as f:
        f.write(f'[Icon Theme]\nName={THEME}\nComment=Invisible cursor for the Clawd Dash kiosk\n')

    lines = []
    if os.path.exists(LABWC_ENV):
        with open(LABWC_ENV) as f:
            lines = [l for l in f.read().splitlines() if not l.startswith('XCURSOR_THEME=')]
    lines.append(f'XCURSOR_THEME={THEME}')
    os.makedirs(os.path.dirname(LABWC_ENV), exist_ok=True)
    with open(LABWC_ENV, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    print(f'Installed {THEME} ({len(names) + 1} cursor names) in {THEME_DIR}')
    print(f'Set XCURSOR_THEME={THEME} in {LABWC_ENV}')
    print('Reboot (or log out and back in) for it to take effect.')


if __name__ == '__main__':
    main()
