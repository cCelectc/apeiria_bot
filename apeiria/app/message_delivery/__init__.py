"""Application-level outbound message delivery boundary."""

from .models import (
    MessageDeliveryChannel,
    MessageDeliveryRequest,
    MessageDeliveryResult,
    MessageDeliveryTarget,
)
from .service import MessageDeliveryService, message_delivery_service

__all__ = [
    "MessageDeliveryChannel",
    "MessageDeliveryRequest",
    "MessageDeliveryResult",
    "MessageDeliveryService",
    "MessageDeliveryTarget",
    "message_delivery_service",
]
