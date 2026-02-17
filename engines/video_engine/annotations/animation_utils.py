import numpy as np

def pulse_color(base_color, t, speed=4):
    factor = 0.5 + 0.5 * np.sin(t * speed)
    return tuple(int(c * factor) for c in base_color)


def fade_opacity(t, duration):
    if t < 0.3:
        return t / 0.3
    return 1