
# 🌒 Nightline

*Nightline is a modern Event Listening framework based on Pydantic.*


Supports:

* ✅ AWS Simple Queue Service (SQS)
* 🚧 Google PubSub
* 🚧 RabbitMQ

**Submit an issue for more integrations!**

## Example

```python
from nightline.services.sqs import AWSSQSEventStreamListener
from pydantic import BaseModel

class OrderMessage(BaseModel):
    order_id: int
    total: float
    items: list[str]
    

listener = AWSSQSEventStreamListener(queue_url="https://your_queue_url")


def process_message(message: OrderMessage):
    print(f"Processing order {message.order_id}")

listener.listen(process_message)
```

## Installation

```
pip install nightline[sqs] # For SQS Support
```

## Contribution

Contributions are more than welcome! Please open an issue on Github.

### Support

For support, please open an issue!

### Inspirations

This project has been heavily inspired by [FastAPI](https://fastapi.tiangolo.com/), we couldn't have done it without them.
