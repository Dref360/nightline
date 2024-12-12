import json
import threading
from typing import Any, Dict, List

import boto3
import pytest
from moto import mock_aws
from pydantic import BaseModel

from nightline.services.sqs import AWSSQSEventStreamListener, EventStreamConfig


class UserAction(BaseModel):
    user_id: int
    action: str


@pytest.fixture
def mock_sqs_environment():
    """
    Fixture to set up and tear down a mock SQS environment

    Yields:
        tuple: (sqs_client, queue_url)
    """
    # Start moto mock for SQS
    with mock_aws():
        # Create SQS client
        sqs_client = boto3.client("sqs", region_name="us-east-1")

        # Create a test queue
        queue_response = sqs_client.create_queue(QueueName="test-queue")
        queue_url = queue_response["QueueUrl"]

        yield sqs_client, queue_url
        sqs_client.close()


@pytest.fixture
def queue_messages(mock_sqs_environment):
    """
    Fixture that returns a function to queue messages

    Args:
        mock_sqs_environment: Fixture with SQS client and queue URL

    Returns:
        Callable: Function to queue messages in the test queue
    """
    sqs_client, queue_url = mock_sqs_environment

    def _queue_messages(messages: List[Dict[str, Any]]):
        """
        Queue messages to the SQS queue

        Args:
            messages: List of messages to queue

        Returns:
            tuple: (queue_url, queued_messages)
        """
        # Send messages to the queue
        for msg in messages:
            sqs_client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(msg))

        return queue_url, messages

    return _queue_messages


def test_listener_basic_functionality(queue_messages):
    """
    Test basic message listening and processing

    Args:
        queue_messages: Fixture to queue messages
    """
    test_messages = [
        {"user_id": 1, "action": "login"},
        {"user_id": 2, "action": "logout"},
    ]

    # Queue the test messages
    queue_url, _ = queue_messages(test_messages)

    # Processed messages container
    processed_messages: List[UserAction] = []

    # Create a threading event to signal test completion
    processing_complete = threading.Event()

    # Create listener
    listener = AWSSQSEventStreamListener(
        queue_url=queue_url,
        config=EventStreamConfig(
            max_workers=1, max_messages=2, wait_time_seconds=1, auto_ack=True
        ),
    )

    def message_handler(message: UserAction):
        """Handler to collect processed messages"""
        processed_messages.append(message)

        # Stop listener after processing both messages
        if len(processed_messages) == 2:
            processing_complete.set()

    # Start listener in a separate thread
    listener_thread = threading.Thread(
        target=listener.listen,
        kwargs={"handler": message_handler, "error_handler": None},
    )
    listener_thread.start()

    # Wait for processing to complete (with timeout)
    assert processing_complete.wait(timeout=5), "Processing did not complete in time"

    # Verify messages were processed
    assert len(processed_messages) == 2
    assert [d.model_dump() for d in processed_messages] == test_messages


def test_error_handling(queue_messages, mocker):
    """
    Test error handling in message processing

    Args:
        queue_messages: Fixture to queue messages
        mocker: pytest-mock fixture
    """
    test_message = [{"user_id": 1, "action": "login"}]
    queue_url, _ = queue_messages(test_message)

    def handler(data: UserAction):
        raise ValueError("Test Error")

    # Create mocks for tracking
    error_handler_mock = mocker.Mock()

    # Create listener
    listener = AWSSQSEventStreamListener(
        queue_url=queue_url,
        config=EventStreamConfig(
            max_workers=1, max_messages=1, wait_time_seconds=1, auto_ack=True
        ),
    )

    # Create a threading event to signal test completion
    processing_complete = threading.Event()

    def error_handler(exception):
        """Capture and handle errors"""
        error_handler_mock(exception)
        processing_complete.set()

    # Start listener in a separate thread
    listener_thread = threading.Thread(
        target=listener.listen,
        kwargs={"handler": handler, "error_handler": error_handler},
    )
    listener_thread.start()

    # Wait for processing to complete (with timeout)
    assert processing_complete.wait(
        timeout=5
    ), "Error handling did not complete in time"

    # Verify mock were called
    error_handler_mock.assert_called_once()


def test_configuration_options(queue_messages):
    """
    Test different configuration options

    Args:
        queue_messages: Fixture to queue messages
    """
    test_messages = [{"user_id": i, "action": f"action-{i}"} for i in range(5)]

    # Queue messages
    queue_url, _ = queue_messages(test_messages)

    # Processed messages container
    processed_messages: List[UserAction] = []

    # Create a threading event to signal test completion
    processing_complete = threading.Event()

    # Create listener with specific configuration
    listener = AWSSQSEventStreamListener(
        queue_url=queue_url,
        config=EventStreamConfig(
            max_workers=2,  # Multiple workers
            max_messages=3,  # Batch size
            wait_time_seconds=1,
            auto_ack=True,
        ),
    )

    def message_handler(message: UserAction):
        """Handler to collect processed messages"""
        processed_messages.append(message)

        # Stop listener after processing all messages
        if len(processed_messages) == len(test_messages):
            processing_complete.set()

    # Start listener in a separate thread
    listener_thread = threading.Thread(
        target=listener.listen,
        kwargs={"handler": message_handler, "error_handler": None},
    )
    listener_thread.start()

    # Wait for processing to complete (with timeout)
    assert processing_complete.wait(timeout=10), "Processing did not complete in time"

    # Verify all messages were processed
    assert len(processed_messages) == len(test_messages)

    # Verify messages match original
    assert [d.model_dump() for d in processed_messages] == test_messages
