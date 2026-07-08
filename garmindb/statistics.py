"""Enumeration of types of statistcs that can be downloaded and processed."""

__author__ = "Tom Goetz"
__copyright__ = "Copyright Tom Goetz"
__license__ = "GPL"


import enum


class Statistics(enum.Enum):
    """The types of statistics that can be downloaded and analyzed."""

    monitoring = 1
    steps = 2
    itime = 3
    sleep = 4
    rhr = 5
    weight = 6
    activities = 7
    hrv = 8
    training_readiness = 9
    training_status = 10
    endurance_score = 11
    hill_score = 12
    lactate_threshold = 13
    body_battery = 14
    body_composition = 15
    fitness_age = 16
    running_predictions = 17

    @classmethod
    def from_string(cls, string):
        """Return a Statistics created from a string that matches an enum name of value."""
        try:
            return cls(string)
        except Exception:
            return getattr(cls, string)
