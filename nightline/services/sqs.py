import json
from typing import Callable, Optional

from nightline.services.core import AbstractEventStreamListener, EventStreamConfig

try:
    import boto3
except ImportError:
    raise EnvironmentError(
        "`boto3` not found, please install `nightline[sqs]` or `nightline[all]`"
    )


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
        error_handler: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """
        Listen to SQS queue and process messages.

        Args:
            handler: Callback to process each message
            error_handler: Optional callback to handle processing errors
        """
        while True:
            response = self._sqs_client.receive_message(
                QueueUrl=self._queue_url,
                MaxNumberOfMessages=self.config.max_messages,
                WaitTimeSeconds=self.config.wait_time_seconds,
            )

            for message in response.get("Messages", []):
                # Submit message processing to thread pool
                future = self._executor.submit(
                    self._process_message,
                    json.loads(message["Body"]),
                    handler,
                    error_handler,
                )

                # Automatically acknowledge if configured
                if self.config.auto_ack:
                    future.add_done_callback(
                        lambda _: self._sqs_client.delete_message(
                            QueueUrl=self._queue_url,
                            ReceiptHandle=message["ReceiptHandle"],
                        )
                    )
