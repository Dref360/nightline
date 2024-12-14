# Getting Started

## Overview

Nightline is a Python library designed to simplify event streaming and message processing, with a focus on making AWS SQS (and others) event handling straightforward and efficient.

## Installation

Install Nightline using pip:

```bash
pip install nightline
```

## Quick Start

### Basic Usage

Here's a simple example of how to use Nightline to listen to an SQS queue and process messages:

```python
from nightline.services.sqs import AWSSQSEventStreamListener
from pydantic import BaseModel

# Define your message model
class OrderMessage(BaseModel):
    order_id: int
    total: float
    items: list[str]

# Create a listener for your SQS queue
listener = AWSSQSEventStreamListener(queue_url="https://your_queue_url")

# Define a message processing function
def process_message(message: OrderMessage):
    print(f"Processing order {message.order_id}")
    # Add your message processing logic here

# Start listening for messages
listener.listen(process_message)
```

## Configuration

Nightline allows you to customize the event stream listener with a configuration object:

```python
from nightline.services.sqs import AWSSQSEventStreamListener, EventStreamConfig

# Create a custom configuration
config = EventStreamConfig(
    max_workers=4,           # Increase concurrent processors
    max_messages=20,         # Retrieve more messages per batch
    wait_time_seconds=30,    # Longer polling interval
    auto_ack=True            # Automatically acknowledge processed messages
)

# Create listener with custom configuration
listener = AWSSQSEventStreamListener(
    queue_url="https://your_queue_url", 
    config=config
)
```

## Configuration Options

The `EventStreamConfig` allows you to fine-tune your event stream processing:

- `max_workers`: Controls the number of concurrent message processors
  - Default: 2
  - Increases parallelism for faster message processing

- `max_messages`: Limits the number of messages retrieved in a single batch
  - Default: 10
  - Helps manage memory and processing load

- `wait_time_seconds`: Sets the long polling wait time for message retrieval
  - Default: 20 seconds
  - Reduces API calls and improves responsiveness

- `auto_ack`: Determines automatic message acknowledgment
  - Default: True
  - When enabled, successfully processed messages are automatically removed from the queue

## Best Practices

1. **Message Model**: Always use a well-defined Pydantic model to validate incoming messages
2. **Error Handling**: Implement robust error handling in your `process_message` function
3. **Logging**: Add logging to track message processing and potential issues
4. **Scalability**: Adjust `max_workers` based on your processing requirements

## Advanced Usage

For more complex scenarios, you can perform custom error handling:

```python
from nightline.services.sqs import AWSSQSEventStreamListener
import logging

def on_error(error: Exception, message: dict):
        logging.error(f"Failed to process message: {error}")
        # Implement custom error handling logic

listener = AWSSQSEventStreamListener(queue_url="https://your_queue_url")
listener.listen(process_message, error_handler=on_error)
```

## Requirements

- Python 3.10+
- AWS SDK for Python (Boto3)
- Pydantic

## Troubleshooting

- Ensure AWS credentials are properly configured
- Check queue URL and permissions
- Verify message format matches your defined model

## Contributing

Contributions are welcome! Please check our GitHub repository for guidelines.

## License

This package is released under Apache V2.