"""Fit plan notation in paper points, keeping its RP-2 axis and unit number.

The body number is fixed. Colour travels forward; the complete control stack
travels backward, with its containers and text together. Nothing is discarded.
"""
import math
from reportlab.pdfbase.pdfmetrics import stringWidth


class _Recorder:
    def __init__(self, sheet):
        self.pt_per_ft = sheet.pt_per_ft
        self.groups = {"front": [], "fixed": [], "back": []}
        self.phase = "front"

    def notation_phase(self, phase):
        self.phase = phase

    def text(self, *args, **kwargs):
        self.groups[self.phase].append(("text", args, kwargs))

    def _shape(self, name, args, kwargs):
        self.groups["back"].append((name, args, kwargs))

    def line(self, *args, **kwargs):
        self._shape("line", args, kwargs)

    def rect(self, *args, **kwargs):
        self._shape("rect", args, kwargs)

    def circle(self, *args, **kwargs):
        self._shape("circle", args, kwargs)


def queue(sheet, draw, x, y, **kwargs):
    """Collect one unit's notation; flush after every unit has been collected."""
    recorder = _Recorder(sheet)
    draw(recorder, x, y, **kwargs)
    angle = math.radians(kwargs.get("rotate_deg", 0.0))
    axis = (-math.sin(angle), math.cos(angle))
    sheet._pending_notation.append((recorder.groups, axis))


def _boxes(sheet, commands):
    """Footprints in stage feet, measured from the fonts' paper dimensions."""
    scale = sheet.pt_per_ft
    boxes = []
    for name, args, kw in commands:
        if name == "text":
            x, y, text = args
            size = kw.get("size", 8)
            font = "Helvetica-Bold" if kw.get("bold") else "Helvetica"
            width = stringWidth(str(text), font, size) / scale
            how = kw.get("align") or ("center" if kw.get("center") else "left")
            x -= width / 2 if how == "center" else width if how == "right" else 0
            # Sheet.text centres by lowering the baseline by size/3. Include
            # full ascender/descender extents, not just the visible cap height.
            y -= size / (3 * scale) if how == "center" else 0
            boxes.append((x, y - .30 * size / scale,
                          x + width, y + 1.08 * size / scale))
        elif name == "line":
            x1, y1, x2, y2 = args
            boxes.append((min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
        elif name == "rect":
            x, y, width, height = args
            boxes.append((x, y, x + width, y + height))
        elif name == "circle":
            x, y, radius = args
            boxes.append((x - radius, y - radius, x + radius, y + radius))
        else:
            raise ValueError(f"Unsupported notation primitive: {name}")
    return boxes


def _shift(box, dx, dy):
    return box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy


def _touches(a, b, pad):
    return (a[0] < b[2] + pad and b[0] < a[2] + pad
            and a[1] < b[3] + pad and b[1] < a[3] + pad)


def _draw(sheet, commands, dx=0.0, dy=0.0):
    for name, args, kwargs in commands:
        args = list(args)
        args[0] += dx
        args[1] += dy
        if name == "line":
            args[2] += dx
            args[3] += dy
        getattr(sheet, name)(*args, **kwargs)


def flush(sheet):
    """Reserve every body number first, then fit front and rear annotations."""
    pending = sheet._pending_notation
    taken = [box for groups, _ in pending for box in _boxes(sheet, groups["fixed"])]
    with sheet.on_layer("labels"):
        for groups, _ in pending:
            _draw(sheet, groups["fixed"])
        for groups, axis in pending:
            for phase, sign in (("front", -1), ("back", 1)):
                commands = groups[phase]
                boxes = _boxes(sheet, commands)
                if not boxes:
                    continue
                # Move only outward. Jump past colliding boxes on a paper-point
                # grid; finite obstacles always have a clear slot along this ray.
                distance = 0.0
                vx, vy = (sign * a for a in axis)
                pad = 1 / sheet.pt_per_ft
                while True:
                    dx, dy = distance * vx, distance * vy
                    shifted = [_shift(b, dx, dy) for b in boxes]
                    collisions = [(a, b) for a in shifted for b in taken
                                  if _touches(a, b, pad)]
                    if not collisions:
                        break
                    jumps = []
                    for a, b in collisions:
                        exits = []
                        for velocity, lo, hi in ((vx, 0, 2), (vy, 1, 3)):
                            if velocity > 1e-9:
                                exits.append((b[hi] + pad - a[lo]) / velocity)
                            elif velocity < -1e-9:
                                exits.append((b[lo] - pad - a[hi]) / velocity)
                        jumps.append(min(exits))
                    distance += max(1.0, math.ceil(max(jumps) * sheet.pt_per_ft)) / sheet.pt_per_ft
                _draw(sheet, commands, dx, dy)
                taken.extend(shifted)
    pending.clear()
