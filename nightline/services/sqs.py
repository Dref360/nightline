import concurrent.futures
import json
from typing import Callable, Dict, Optional

import structlog

from nightline.services.core import AbstractEventStreamListener, EventStreamConfig

try:
    import boto3
except ImportError:
    raise EnvironmentError(
        "`boto3` not found, please install `nightline[sqs]` or `nightline[all]`"
    )

log = structlog.get_logger(__name__)


def done_callback_logging(ft: concurrent.futures.Future):
    if e := ft.exception():
        log.error("Error during processing", exc_info=e)


class AWSSQSEventStreamListener(AbstractEventStreamListener):
    """
    Event stream listener for AWS SQS.
    """

    def __init__(self, queue_url: str, config: Optional[EventStreamConfig] = None):
        """
        Initialize SQS event stream listener.

        Args:
            queue_url: SQS queue URL to listen to
            config: Optional configuration for the listener
        """
        super().__init__(config or EventStreamConfig())
        self._sqs_client = boto3.client("sqs")
        self._queue_url = queue_url

    def listen(
        self,
        handler: Callable,
        error_handler: Optional[Callable[[Exception, Dict], None]] = None,
    ) -> None:
        """
        Listen to SQS queue and process messages.

        Args:
            handler: Callback to process each message
            error_handler: Optional callback to handle processing errors
        """
        while not self._stop_signal.is_set():
            response = self._sqs_client.receive_message(
                QueueUrl=self._queue_url,
                MessageAttributeNames=["All"],
                MaxNumberOfMessages=self.config.max_messages,
                WaitTimeSeconds=self.config.wait_time_seconds,
            )

            for message in response.get("Messages", []):
                try:
                    json_obj = json.loads(message["Body"])
                    json_headers = message.get("MessageAttributes", {})
                except json.JSONDecodeError:
                    log.warning("Couldn't decode message to JSON")
                    continue

                # Submit message processing to thread pool
                future = self._executor.submit(
                    self._process_message,
                    json_obj,
                    json_headers,
                    handler,
                    error_handler,
                )
                # Some logs at the end
                future.add_done_callback(done_callback_logging)

                # Automatically acknowledge if configured
                if self.config.auto_ack:
                    future.add_done_callback(
                        lambda _: self._sqs_client.delete_message(
                            QueueUrl=self._queue_url,
                            ReceiptHandle=message["ReceiptHandle"],
                        )
                    )
