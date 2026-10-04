"""
Description:
Stateless helpers shared across the application, split by the KIND of value they work on
(`time.py`, and whatever follows) rather than by which layer calls them.

Nothing here decides anything or touches I/O: a helper lands in this package precisely because it
has no place in the domain, no transport to talk to, and more than one caller.
"""
