import abc
import inspect
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Dict, Optional, Type, Union

import structlog
from pydantic import BaseModel

from nightline.types import Headers

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
    wait_time_seconds: int = 10
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
        self._stop_signal = threading.Event()

    @abc.abstractmethod
    def listen(
        self,
        handler: Callable,
        error_handler: Optional[Callable[[Exception, Dict], None]] = None,
    ) -> None:
        """
        Start listening to the event stream and process messages.

        Args:
            handler: Callback function to process each message
            error_handler: Optional callback to handle processing errors
        """
        pass

    def stop(self):
        self._stop_signal.set()

    @lru_cache
    def get_message_typing(
        self, handler: Callable
    ) -> Dict[str, Union[Type[BaseModel], Type[Headers]]]:
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
        parameters = sig.parameters

        if any(
            missing := [
                n
                for n, p in parameters.items()
                if p.annotation == inspect.Parameter.empty
            ]
        ):
            raise ValueError(f"Type annotations required for {missing}")

        # Check if there are any parameters
        if not parameters:
            raise ValueError("Handler must have at least one argument")

        if not any(issubclass(p.annotation, BaseModel) for p in parameters.values()):
            raise ValueError(
                "At least one parameters must be a Pydantic BaseModel to convert the message"
            )

        unauthorized_types = [
            (n, p.annotation)
            for n, p in parameters.items()
            if not issubclass(p.annotation, (BaseModel, Headers))
        ]
        if unauthorized_types:
            raise ValueError(
                f"Supported types include `pydantic.BaseModel` and `nightline.Headers`, but found {unauthorized_types}"
            )

        # All verifications done, found all types.
        return {n: p.annotation for n, p in parameters.items()}

    def _process_message(
        self,
        message: Dict,
        headers: Dict,
        handler: Callable,
        error_handler: Optional[Callable[[Exception, Dict], None]] = None,
    ) -> None:
        """
        Process a single message with error handling.

        Args:
            message: Message to process
            handler: Message processing function
            error_handler: Optional error handling function
        """
        try:
            type_mapping = self.get_message_typing(handler)
            params = {
                n: t(**message) if issubclass(t, BaseModel) else headers
                for n, t in type_mapping.items()
            }
            handler(**params)
            log.info("200 - Success")
        except Exception as e:
            if error_handler:
                error_handler(e, message)
            else:
                log.error("500 - Error", exc_info=e)
                raise
