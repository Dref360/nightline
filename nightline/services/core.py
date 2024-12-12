import abc
import inspect
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Dict, Optional, Type

import structlog

log = structlog.get_logger(__name__)


@dataclass
class EventStreamConfig:
    """
    Configuration for event stream listeners.

    Attributes:
        max_workers: Maximum number of concurrent message processors
        max_messages: Maximum number of messages to retrieve in a single batch
        wait_time_seconds: Long polling wait time for message retrieval
        auto_ack: Whether to automatically acknowledge messages after processing
    """

    max_workers: int = 2
    max_messages: int = 10
    wait_time_seconds: int = 20
    auto_ack: bool = True


class AbstractEventStreamListener(abc.ABC):
    """
    Abstract base class for event stream listeners.
    Provides a unified interface for different event stream services.
    """

    def __init__(self, config: Optional[EventStreamConfig] = None):
        """
        Initialize the event stream listener.

        Args:
            config: Configuration for the event stream listener
        """
        self.config = config or EventStreamConfig()
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_workers)

    @abc.abstractmethod
    def listen(
        self,
        handler: Callable,
        error_handler: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Start listening to the event stream and process messages.

        Args:
            handler: Callback function to process each message
            error_handler: Optional callback to handle processing errors
        """
        pass

    @lru_cache
    def get_message_typing(self, handler: Callable) -> Optional[Type]:
        """
        Extract the type annotation of the first argument of the handler.

        Args:
            handler: The message handling function

        Returns:
            Type: The type annotation of the first argument

        Raises:
            ValueError: If no type annotation is found or handler has no arguments
        """
        # Get the signature of the handler
        sig = inspect.signature(handler)

        # Get the parameters
        parameters = list(sig.parameters.values())

        # Check if there are any parameters
        if not parameters:
            raise ValueError("Handler must have at least one argument")

        # Get the first parameter
        first_param = parameters[0]

        # Check if the first parameter has a type annotation
        if first_param.annotation == inspect.Parameter.empty:
            raise ValueError("First argument must have a type annotation")

        return first_param.annotation

    def _process_message(
        self,
        message: Dict,
        handler: Callable,
        error_handler: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Process a single message with error handling.

        Args:
            message: Message to process
            handler: Message processing function
            error_handler: Optional error handling function
        """
        try:
            type_annot = self.get_message_typing(handler)
            converted = type_annot(**message)
            handler(converted)
        except Exception as e:
            if error_handler:
                error_handler(e)
            else:
                raise
