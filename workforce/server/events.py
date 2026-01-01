"""Event system for decoupling scheduling logic from transport layer."""

import json
import logging
import os
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

logger = logging.getLogger(__name__)

EventType = Literal[
    "NODE_READY",
    "NODE_STARTED",
    "NODE_FINISHED",
    "NODE_FAILED",
    "RUN_COMPLETE",
    "GRAPH_UPDATED",
]


@dataclass
class Event:
    """Domain event representing something that happened in the workflow system.
    
    This is NOT a transport message - it's a semantic fact about state changes.
    Subscribers decide how to communicate these facts to their respective clients.
    """
    type: EventType
    payload: dict


class EventBus:
    """Simple event bus for pub-sub within the server process.
    
    Subscribers register handlers for specific event types.
    When events are emitted, all registered handlers are called.
    Handlers that raise exceptions are logged but don't prevent other handlers from running.
    """
    
    def __init__(self, log_file: str | None = None, max_log_size: int = 10 * 1024 * 1024):
        """Initialize the event bus.
        
        Args:
            log_file: Path to JSON log file for event persistence. If None, no logging.
            max_log_size: Maximum log file size in bytes before rotation (default 10MB).
        """
        self._subscribers: dict[EventType, list[Callable]] = defaultdict(list)
        self._log_file = log_file
        self._max_log_size = max_log_size
        
        if self._log_file:
            # Ensure log directory exists
            Path(self._log_file).parent.mkdir(parents=True, exist_ok=True)
    
    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Register a handler to be called when events of this type are emitted.
        
        Args:
            event_type: The type of event to listen for.
            handler: Callable that takes an Event and returns None.
        """
        self._subscribers[event_type].append(handler)
        handler_name = getattr(handler, '__name__', repr(handler))
        logger.debug(f"Subscribed handler {handler_name} to {event_type}")
    
    def emit(self, event: Event) -> None:
        """Emit an event to all registered subscribers.
        
        Handlers are called synchronously in registration order.
        If a handler raises an exception, it's logged and other handlers continue.
        
        Args:
            event: The event to emit.
        """
        # Log to file first if configured
        if self._log_file:
            self._log_event(event)
        
        # Notify all subscribers
        handlers = self._subscribers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"Handler {handler.__name__} failed for event {event.type}: {e}",
                    exc_info=True
                )
    
    def _log_event(self, event: Event) -> None:
        """Append event to JSON log file with rotation."""
        try:
            # Check if rotation is needed
            if os.path.exists(self._log_file):
                file_size = os.path.getsize(self._log_file)
                if file_size >= self._max_log_size:
                    self._rotate_log()
            
            # Append event as JSON line
            with open(self._log_file, 'a') as f:
                log_entry = {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'type': event.type,
                    'payload': event.payload
                }
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to log event to {self._log_file}: {e}")
    
    def _rotate_log(self) -> None:
        """Rotate log file by renaming to .1, .2, etc."""
        try:
            # Find next rotation number
            base = self._log_file
            rotation_num = 1
            while os.path.exists(f"{base}.{rotation_num}"):
                rotation_num += 1
            
            # Rotate
            os.rename(self._log_file, f"{base}.{rotation_num}")
            logger.info(f"Rotated event log to {base}.{rotation_num}")
        except Exception as e:
            logger.error(f"Failed to rotate log file: {e}")
