def format_duration(seconds: float) -> str:   # e.g. 3847.2
    """
    Description:
    Renders an elapsed time the way it is easiest to read at a glance: seconds while the run is
    short, minutes once it stops being, hours when a local model is grinding through a corpus.
    A bare "3847.2s" forces the reader to do the division.

    The thresholds match the runs this project actually has: a hosted model finishes a ticket in
    seconds, a 4.5B model on CPU takes minutes, and a corpus run takes hours.

    Example args:
        seconds=3847.2

    Example result:
        '1h 04min'
    """
    if seconds < 90:
        return f"{seconds:.0f}s"

    minutes, secs = divmod(int(seconds), 60)

    if minutes < 60:
        return f"{minutes}min {secs:02d}s"

    hours, mins = divmod(minutes, 60)

    return f"{hours}h {mins:02d}min"
