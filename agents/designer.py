"""Produce a validated Markdown specification for a UI task."""

from agents.base import Agent
from core.schema import Agent as Role


class Designer(Agent):
    """Run the Designer prompt with the shared input and retry logic."""

    def __init__(self) -> None:
        super().__init__(Role.DESIGNER)
