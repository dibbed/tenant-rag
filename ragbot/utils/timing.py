"""Performance timing utilities for measuring response times."""

import time
from typing import Dict, Optional
from contextlib import contextmanager
from ragbot.outputs.logger import logger


class PerformanceTimer:
    """Timer for measuring bot response times"""

    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.checkpoints: Dict[str, float] = {}

    def start(self) -> None:
        """Start timing"""
        self.start_time = time.time()
        self.checkpoints["start"] = self.start_time
        logger.info(f"⏱️ Timer started at {self.start_time:.6f}")

    def checkpoint(self, name: str) -> None:
        """Add a timing checkpoint"""
        current_time = time.time()
        self.checkpoints[name] = current_time

        if len(self.checkpoints) > 1:
            # Find the most recent checkpoint before this one
            prev_checkpoint = self.start_time
            for checkpoint_name, checkpoint_time in self.checkpoints.items():
                if checkpoint_name != name and checkpoint_time < current_time:
                    if checkpoint_time > prev_checkpoint:
                        prev_checkpoint = checkpoint_time

            duration = current_time - prev_checkpoint
            if duration >= 0:  # Only log positive durations
                logger.info(f"⏱️ Checkpoint '{name}': {duration:.4f}s")

    def end(self) -> float:
        """End timing and return total duration"""
        self.end_time = time.time()
        self.checkpoints["end"] = self.end_time

        if self.start_time:
            total_duration = self.end_time - self.start_time
            logger.info(f"⏱️ Total response time: {total_duration:.4f}s")
            return total_duration
        return 0.0

    def get_duration(self) -> float:
        """Get total duration"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0

    def get_checkpoint_duration(self, checkpoint_name: str) -> float:
        """Get duration from start to specific checkpoint"""
        if self.start_time and checkpoint_name in self.checkpoints:
            return self.checkpoints[checkpoint_name] - self.start_time
        return 0.0

    def get_summary(self) -> str:
        """Get timing summary"""
        if not self.start_time:
            return "Timer not started"

        summary = "⏱️ Response Time Summary:\n"
        summary += f"📊 Total: {self.get_duration():.4f}s\n"

        prev_time = self.start_time
        for name, timestamp in sorted(self.checkpoints.items()):
            if name != "start":
                duration = timestamp - prev_time
                summary += f"📈 {name}: {duration:.4f}s\n"
                prev_time = timestamp

        return summary


@contextmanager
def measure_response_time(operation_name: str = "operation"):
    """Context manager for measuring response times"""
    timer = PerformanceTimer()
    timer.start()

    try:
        yield timer
    finally:
        duration = timer.end()
        logger.info(f"⏱️ {operation_name} completed in {duration:.4f}s")


def log_timing_details(
    message_type: str,
    user_id: int,
    duration: float,
    checkpoints: Dict[str, float] = None,
) -> None:
    """Log detailed timing information"""

    # Performance thresholds
    excellent = 0.5  # < 0.5s
    good = 1.0  # < 1.0s
    acceptable = 2.0  # < 2.0s
    slow = 5.0  # < 5.0s

    # Determine performance level
    if duration < excellent:
        level = "🚀 Excellent"
        emoji = "🟢"
    elif duration < good:
        level = "✅ Good"
        emoji = "🟡"
    elif duration < acceptable:
        level = "⚠️ Acceptable"
        emoji = "🟠"
    elif duration < slow:
        level = "🐌 Slow"
        emoji = "🔴"
    else:
        level = "🚨 Very Slow"
        emoji = "💀"

    # Log performance
    logger.info(
        f"{emoji} {level} response time: {duration:.4f}s for {message_type} (User: {user_id})"
    )

    # Log checkpoints if available
    if checkpoints:
        logger.info("📊 Timing breakdown:")
        # Sort checkpoints by timestamp
        sorted_checkpoints = sorted(checkpoints.items(), key=lambda x: x[1])
        prev_time = None
        for name, timestamp in sorted_checkpoints:
            if prev_time is not None:
                step_duration = timestamp - prev_time
                if step_duration >= 0:  # Only log positive durations
                    logger.info(f"   📈 {name}: {step_duration:.4f}s")
            prev_time = timestamp


# Global timer instance
response_timer = PerformanceTimer()
