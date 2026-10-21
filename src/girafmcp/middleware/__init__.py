"""Middleware infrastructure for tool call interception.

Provides a composable middleware chain that wraps tool dispatch,
enabling logging, guardrails, resilience testing, and other
cross-cutting concerns.

Example usage:
    chain = MiddlewareChain()
    chain.add(LoggingMiddleware(...))
    chain.add(GuardrailsMiddleware(...))

    # In call_tool:
    ctx = ToolContext(name=name, arguments=arguments, ...)
    result = await chain.execute(ctx, dispatch_fn)
"""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from mcp.types import TextContent

from girafmcp.core.session import SessionState, get_current_session

from .base import Middleware, NextMiddleware, ToolContext

__all__ = [
    "Middleware",
    "MiddlewareChain",
    "NextMiddleware",
    "ToolContext",
    "create_context",
]

logger = logging.getLogger(__name__)


# Type alias for the final dispatch function
DispatchFn = Callable[[str, dict[str, Any]], Awaitable[list[TextContent]]]


class MiddlewareChain:
    """Manages an ordered chain of middleware for tool call processing.

    Middleware is executed in the order added (first added = outermost).
    Each middleware can:
    - Modify the request before passing to next
    - Short-circuit and return without calling next
    - Modify the response after getting it from next
    """

    def __init__(self) -> None:
        self._middlewares: list[Middleware] = []

    def add(self, middleware: Middleware) -> "MiddlewareChain":
        """Add a middleware to the chain.

        Args:
            middleware: The middleware to add

        Returns:
            self for method chaining
        """
        self._middlewares.append(middleware)
        logger.debug(f"Added middleware: {middleware.name}")
        return self

    def remove(self, middleware_type: type[Middleware]) -> bool:
        """Remove a middleware by type.

        Args:
            middleware_type: The class of middleware to remove

        Returns:
            True if removed, False if not found
        """
        for i, m in enumerate(self._middlewares):
            if isinstance(m, middleware_type):
                self._middlewares.pop(i)
                logger.debug(f"Removed middleware: {m.name}")
                return True
        return False

    def clear(self) -> None:
        """Remove all middleware from the chain."""
        self._middlewares.clear()

    @property
    def middlewares(self) -> list[Middleware]:
        """Get list of middleware (for inspection/testing)."""
        return self._middlewares.copy()

    async def execute(
        self,
        ctx: ToolContext,
        dispatch: DispatchFn,
    ) -> list[TextContent]:
        """Execute the middleware chain for a tool call.

        Args:
            ctx: The tool context
            dispatch: The final dispatch function to call the actual handler

        Returns:
            The tool result after processing through all middleware
        """
        # Build the chain from inside out
        # The innermost function calls the actual dispatch
        async def final_dispatch(ctx: ToolContext) -> list[TextContent]:
            try:
                result = await dispatch(ctx.name, ctx.arguments)
                ctx.result = result
                return result
            except Exception as e:
                ctx.error = e
                raise

        # Wrap each middleware around the previous
        next_fn: NextMiddleware = final_dispatch
        for middleware in reversed(self._middlewares):
            # Capture middleware and next_fn in closure
            next_fn = self._wrap_middleware(middleware, next_fn)

        # Execute the chain
        try:
            return await next_fn(ctx)
        except Exception as e:
            # Ensure error is recorded in context
            ctx.error = e
            raise

    def _wrap_middleware(
        self,
        middleware: Middleware,
        next_fn: NextMiddleware,
    ) -> NextMiddleware:
        """Create a wrapper function for a middleware.

        Args:
            middleware: The middleware to wrap
            next_fn: The next function in the chain

        Returns:
            A function that calls the middleware with the next function
        """

        async def wrapper(ctx: ToolContext) -> list[TextContent]:
            if middleware.should_process(ctx):
                return await middleware.process(ctx, next_fn)
            else:
                return await next_fn(ctx)

        return wrapper


def create_context(
    name: str,
    arguments: dict[str, Any],
    session: SessionState | None = None,
) -> ToolContext:
    """Create a ToolContext for a tool invocation.

    Args:
        name: The tool name
        arguments: The tool arguments
        session: Optional session state (defaults to current session)

    Returns:
        A new ToolContext ready for middleware processing
    """
    return ToolContext(
        name=name,
        arguments=arguments,
        session=session or get_current_session(),
        start_time=time.monotonic(),
    )
