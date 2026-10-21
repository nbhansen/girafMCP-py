"""Tests for middleware infrastructure."""

import pytest
from mcp.types import TextContent

from girafmcp.core.session import reset_session
from girafmcp.middleware import (
    Middleware,
    MiddlewareChain,
    ToolContext,
    create_context,
)
from girafmcp.middleware.base import NextMiddleware


class RecordingMiddleware(Middleware):
    """Test middleware that records calls."""

    def __init__(self, name: str = "recorder", shared_calls: list[str] | None = None):
        self._name = name
        self.calls: list[str] = shared_calls if shared_calls is not None else []
        self.contexts: list[ToolContext] = []

    @property
    def name(self) -> str:
        return self._name

    async def process(
        self, ctx: ToolContext, next_middleware: NextMiddleware
    ) -> list[TextContent]:
        self.calls.append(f"{self._name}:before")
        self.contexts.append(ctx)
        result = await next_middleware(ctx)
        self.calls.append(f"{self._name}:after")
        return result


class ModifyingMiddleware(Middleware):
    """Test middleware that modifies responses."""

    def __init__(self, prefix: str = "[modified] "):
        self.prefix = prefix

    async def process(
        self, ctx: ToolContext, next_middleware: NextMiddleware
    ) -> list[TextContent]:
        result = await next_middleware(ctx)
        if result:
            modified_text = self.prefix + result[0].text
            return [TextContent(type="text", text=modified_text)]
        return result


class ShortCircuitMiddleware(Middleware):
    """Test middleware that short-circuits the chain."""

    def __init__(self, response: str = "short-circuited"):
        self.response = response

    async def process(
        self, ctx: ToolContext, next_middleware: NextMiddleware
    ) -> list[TextContent]:
        result = [TextContent(type="text", text=self.response)]
        ctx.result = result
        return result  # Never calls next_middleware


class ConditionalMiddleware(Middleware):
    """Test middleware with conditional processing."""

    def __init__(self, skip_tools: list[str]):
        self.skip_tools = skip_tools
        self.processed: list[str] = []

    def should_process(self, ctx: ToolContext) -> bool:
        return ctx.name not in self.skip_tools

    async def process(
        self, ctx: ToolContext, next_middleware: NextMiddleware
    ) -> list[TextContent]:
        self.processed.append(ctx.name)
        return await next_middleware(ctx)


class TestToolContext:
    """Tests for ToolContext dataclass."""

    def test_create_context(self) -> None:
        """create_context should populate fields correctly."""
        reset_session()
        ctx = create_context("search_code", {"query": "test"})

        assert ctx.name == "search_code"
        assert ctx.arguments == {"query": "test"}
        assert ctx.session is not None
        assert ctx.start_time > 0
        assert ctx.result is None
        assert ctx.error is None

    def test_succeeded_property(self) -> None:
        """succeeded should reflect result/error state."""
        ctx = create_context("test", {})

        assert not ctx.succeeded  # No result yet

        ctx.result = [TextContent(type="text", text="ok")]
        assert ctx.succeeded

        ctx.error = Exception("fail")
        assert not ctx.succeeded  # Error overrides result

    def test_response_text_property(self) -> None:
        """response_text should extract text from result."""
        ctx = create_context("test", {})

        assert ctx.response_text is None

        ctx.result = [TextContent(type="text", text="hello world")]
        assert ctx.response_text == "hello world"


class TestMiddlewareChain:
    """Tests for MiddlewareChain."""

    @pytest.fixture
    def chain(self) -> MiddlewareChain:
        return MiddlewareChain()

    @pytest.fixture
    def dispatch(self):
        async def _dispatch(name: str, args: dict) -> list[TextContent]:
            return [TextContent(type="text", text=f"result:{name}")]

        return _dispatch

    async def test_empty_chain(self, chain: MiddlewareChain, dispatch) -> None:
        """Empty chain should just call dispatch."""
        ctx = create_context("test_tool", {"arg": "value"})
        result = await chain.execute(ctx, dispatch)

        assert len(result) == 1
        assert result[0].text == "result:test_tool"

    async def test_single_middleware(self, chain: MiddlewareChain, dispatch) -> None:
        """Single middleware should wrap dispatch."""
        recorder = RecordingMiddleware("m1")
        chain.add(recorder)

        ctx = create_context("test_tool", {})
        await chain.execute(ctx, dispatch)

        assert recorder.calls == ["m1:before", "m1:after"]
        assert len(recorder.contexts) == 1

    async def test_middleware_order(self, chain: MiddlewareChain, dispatch) -> None:
        """Middleware should execute in order added (first = outermost)."""
        shared_calls: list[str] = []
        r1 = RecordingMiddleware("m1", shared_calls)
        r2 = RecordingMiddleware("m2", shared_calls)
        r3 = RecordingMiddleware("m3", shared_calls)

        chain.add(r1).add(r2).add(r3)

        ctx = create_context("test", {})
        await chain.execute(ctx, dispatch)

        # First added is outermost, so m1 before/after wraps m2 wraps m3
        assert shared_calls == [
            "m1:before",
            "m2:before",
            "m3:before",
            "m3:after",
            "m2:after",
            "m1:after",
        ]

    async def test_middleware_can_modify_response(
        self, chain: MiddlewareChain, dispatch
    ) -> None:
        """Middleware can modify the response."""
        chain.add(ModifyingMiddleware("[outer] "))
        chain.add(ModifyingMiddleware("[inner] "))

        ctx = create_context("test", {})
        result = await chain.execute(ctx, dispatch)

        # Inner modifies first, then outer
        assert result[0].text == "[outer] [inner] result:test"

    async def test_middleware_can_short_circuit(
        self, chain: MiddlewareChain, dispatch
    ) -> None:
        """Middleware can short-circuit and skip remaining chain."""
        recorder = RecordingMiddleware("after_short")
        chain.add(recorder)
        chain.add(ShortCircuitMiddleware("blocked"))

        ctx = create_context("test", {})
        result = await chain.execute(ctx, dispatch)

        assert result[0].text == "blocked"
        # Recorder still sees before/after, but dispatch was never called
        assert recorder.calls == ["after_short:before", "after_short:after"]
        # Context should have result set
        assert ctx.result is not None

    async def test_should_process_skips_middleware(
        self, chain: MiddlewareChain, dispatch
    ) -> None:
        """should_process=False should skip that middleware."""
        conditional = ConditionalMiddleware(skip_tools=["skip_me"])
        chain.add(conditional)

        ctx1 = create_context("process_me", {})
        await chain.execute(ctx1, dispatch)
        assert conditional.processed == ["process_me"]

        ctx2 = create_context("skip_me", {})
        await chain.execute(ctx2, dispatch)
        # Should not have processed skip_me
        assert conditional.processed == ["process_me"]

    async def test_error_propagation(self, chain: MiddlewareChain) -> None:
        """Errors should propagate and be recorded in context."""

        async def failing_dispatch(name: str, args: dict) -> list[TextContent]:
            raise ValueError("dispatch failed")

        recorder = RecordingMiddleware("m1")
        chain.add(recorder)

        ctx = create_context("test", {})
        with pytest.raises(ValueError, match="dispatch failed"):
            await chain.execute(ctx, failing_dispatch)

        # Error should be recorded in context
        assert ctx.error is not None
        assert str(ctx.error) == "dispatch failed"

    def test_add_returns_chain(self, chain: MiddlewareChain) -> None:
        """add() should return chain for fluent interface."""
        result = chain.add(RecordingMiddleware())
        assert result is chain

    def test_remove_middleware(self, chain: MiddlewareChain) -> None:
        """remove() should remove middleware by type."""
        r1 = RecordingMiddleware("r1")
        m1 = ModifyingMiddleware()
        chain.add(r1).add(m1)

        assert len(chain.middlewares) == 2

        removed = chain.remove(ModifyingMiddleware)
        assert removed is True
        assert len(chain.middlewares) == 1
        assert chain.middlewares[0] is r1

        removed_again = chain.remove(ModifyingMiddleware)
        assert removed_again is False

    def test_clear(self, chain: MiddlewareChain) -> None:
        """clear() should remove all middleware."""
        chain.add(RecordingMiddleware()).add(ModifyingMiddleware())
        assert len(chain.middlewares) == 2

        chain.clear()
        assert len(chain.middlewares) == 0

    def test_middlewares_property_returns_copy(
        self, chain: MiddlewareChain
    ) -> None:
        """middlewares property should return a copy."""
        r1 = RecordingMiddleware()
        chain.add(r1)

        middlewares = chain.middlewares
        middlewares.append(ModifyingMiddleware())

        # Original chain should be unchanged
        assert len(chain.middlewares) == 1
