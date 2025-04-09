"""Service for optimizing API requests with adaptive rate limiting.

This module provides a service to manage API rate limits by dynamically adjusting
request intervals based on server responses.
"""

import logging
import random
import time
from collections.abc import Callable
from typing import Any, TypeVar

# Type variable for generic function return type
T = TypeVar("T")

# Configure logger
logger = logging.getLogger(__name__)


class AdaptiveRateLimiter:
    """Adaptive rate limiting service to prevent API throttling.

    This service dynamically adjusts request delays based on API responses,
    backing off when rate limits are hit and gradually reducing delays when
    requests succeed.
    """

    def __init__(
        self,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        min_delay: float = 0.5,
        backoff_factor: float = 2.0,
        recovery_factor: float = 0.95,
        max_retries: int = 15,
        jitter: float = 0.25,
    ) -> None:
        """Initialize the adaptive rate limiter.

        Args:
            initial_delay: Initial delay between requests in seconds
            max_delay: Maximum delay between requests in seconds
            min_delay: Minimum delay between requests in seconds
            backoff_factor: Multiplier for delay when rate limit is hit
            recovery_factor: Multiplier for delay when request succeeds
            max_retries: Maximum number of retries for a single request
            jitter: Random jitter factor to add to delays (0-1.0) to prevent synchronized requests
        """
        self.current_delay = initial_delay
        self.max_delay = max_delay
        self.min_delay = min_delay
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        self.max_retries = max_retries
        self.jitter = jitter
        self.last_request_time: dict[str, float] = {}
        # Track consecutive successes and failures for better adaptation
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        # Use a global delay floor that increases with sustained pressure
        self.global_delay_floor = min_delay

    def _apply_jitter(self, delay: float) -> float:
        """Apply random jitter to delay to prevent synchronized requests.

        Args:
            delay: Base delay time in seconds

        Returns
        -------
            Delay with jitter applied
        """
        if self.jitter <= 0:
            return delay

        jitter_amount = delay * self.jitter
        return delay + random.uniform(-jitter_amount / 2, jitter_amount)

    def execute_with_rate_limit(
        self, func: Callable[..., T], endpoint_key: str, *args: Any, **kwargs: Any
    ) -> T:
        """Execute a function with adaptive rate limiting.

        Args:
            func: The function to execute
            endpoint_key: A unique key identifying the endpoint being accessed
            args: Positional arguments to pass to the function
            kwargs: Keyword arguments to pass to the function

        Returns
        -------
            The result of the function call

        Raises
        ------
            Exception: Any exception raised by the function after max retries
        """
        # Ensure we wait the minimum time since the last request to this endpoint
        now = time.time()
        if endpoint_key in self.last_request_time:
            time_since_last = now - self.last_request_time[endpoint_key]
            if time_since_last < self.current_delay:
                sleep_time = self._apply_jitter(self.current_delay - time_since_last)
                time.sleep(sleep_time)

        retries = 0
        while retries <= self.max_retries:
            try:
                # Update the last request time
                self.last_request_time[endpoint_key] = time.time()

                # Execute the function
                result = func(*args, **kwargs)

                # Success - gradually reduce delay (but not below min_delay or global floor)
                self.consecutive_successes += 1
                self.consecutive_failures = 0

                if self.consecutive_successes >= 10:
                    # More aggressive recovery after sustained success
                    self.current_delay = max(
                        self.global_delay_floor,
                        self.current_delay * (self.recovery_factor * 0.9),
                    )
                    # Slowly reduce the global floor after sustained success
                    if self.consecutive_successes >= 20:
                        self.global_delay_floor = max(
                            self.min_delay, self.global_delay_floor * 0.95
                        )
                else:
                    # Normal recovery
                    self.current_delay = max(
                        self.global_delay_floor,
                        self.current_delay * self.recovery_factor,
                    )

                return result

            except Exception as e:
                retries += 1
                self.consecutive_successes = 0
                self.consecutive_failures += 1

                # Check if this is a rate limit error
                is_rate_limit = any(
                    rate_term in str(e).lower()
                    for rate_term in ["rate limit", "too many", "429", "throttl"]
                )

                if is_rate_limit:
                    # Rate limit hit - increase delay exponentially
                    self.current_delay = min(
                        self.max_delay, self.current_delay * self.backoff_factor
                    )

                    # Increase global floor on sustained failures
                    if self.consecutive_failures >= 3:
                        self.global_delay_floor = min(
                            self.current_delay * 0.5, self.global_delay_floor * 1.5
                        )

                    logger.warning(
                        f"Rate limit hit for {endpoint_key}. "
                        f"Backing off for {self.current_delay:.2f}s. "
                        f"Retry {retries}/{self.max_retries}, "
                        f"Global floor: {self.global_delay_floor:.2f}s"
                    )

                    # Wait before retrying with jitter
                    time.sleep(self._apply_jitter(self.current_delay))

                elif retries <= self.max_retries:
                    # Other error - retry with backoff, but less aggressive
                    wait_time = self.min_delay * (1.5 ** (retries - 1))

                    logger.warning(
                        f"Error for {endpoint_key}: {e}. "
                        f"Retrying in {wait_time:.2f}s. "
                        f"Retry {retries}/{self.max_retries}"
                    )

                    time.sleep(self._apply_jitter(wait_time))
                else:
                    # Max retries reached for non-rate-limit error
                    logger.error(f"Max retries reached for {endpoint_key}: {e}")
                    raise

        # Max retries reached for rate limit
        raise Exception(f"Max retries ({self.max_retries}) exceeded for {endpoint_key}")
