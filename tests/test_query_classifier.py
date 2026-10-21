"""Tests for query classification service."""


from girafmcp.core.services.query_classifier import (
    classify_query_type,
    detect_meta_skills,
    extract_result_count,
)
from girafmcp.core.types import QueryType


class TestClassifyQueryType:
    """Tests for query type classification."""

    def test_explanation_patterns(self) -> None:
        """Should detect explanation queries."""
        cases = [
            ("search_code", {"query": "explain how the API works"}),
            ("search_code", {"query": "what does this function do"}),
            ("search_code", {"query": "how does authentication work"}),
            ("search_code", {"query": "why does this use a factory pattern"}),
        ]
        for tool, args in cases:
            result = classify_query_type(tool, args)
            assert result == QueryType.EXPLANATION, f"Failed for: {args}"

    def test_generation_patterns(self) -> None:
        """Should detect generation queries."""
        cases = [
            ("search_code", {"query": "write a function to parse JSON"}),
            ("search_code", {"query": "create a new component"}),
            ("search_code", {"query": "implement authentication"}),
            ("search_code", {"query": "generate unit tests"}),
        ]
        for tool, args in cases:
            result = classify_query_type(tool, args)
            assert result == QueryType.GENERATION, f"Failed for: {args}"

    def test_navigation_patterns(self) -> None:
        """Should detect navigation queries."""
        cases = [
            ("search_code", {"query": "find the login function"}),
            ("search_code", {"query": "where is the config file"}),
            ("search_code", {"query": "list all API endpoints"}),
            ("search_code", {"query": "show me the user model"}),
        ]
        for tool, args in cases:
            result = classify_query_type(tool, args)
            assert result == QueryType.NAVIGATION, f"Failed for: {args}"

    def test_debugging_patterns(self) -> None:
        """Should detect debugging queries."""
        cases = [
            ("search_code", {"query": "error when running tests"}),
            ("search_code", {"query": "fix the null pointer exception"}),
            ("search_code", {"query": "code doesn't work"}),
            ("search_code", {"query": "tests are failing"}),
            ("search_code", {"query": "there's a bug in the login"}),
        ]
        for tool, args in cases:
            result = classify_query_type(tool, args)
            assert result == QueryType.DEBUGGING, f"Failed for: {args}"

    def test_verification_patterns(self) -> None:
        """Should detect verification queries."""
        cases = [
            ("search_code", {"query": "is this correct implementation"}),
            ("search_code", {"query": "does this work with async"}),
            ("search_code", {"query": "verify my solution"}),
            ("search_code", {"query": "check if this is right"}),
        ]
        for tool, args in cases:
            result = classify_query_type(tool, args)
            assert result == QueryType.VERIFICATION, f"Failed for: {args}"

    def test_tool_based_classification(self) -> None:
        """Should classify by tool when no query text."""
        assert classify_query_type("list_repositories", {}) == QueryType.NAVIGATION
        assert classify_query_type("list_wiki_pages", {}) == QueryType.NAVIGATION
        assert classify_query_type("get_file", {"path": "src/main.py"}) == QueryType.NAVIGATION
        assert classify_query_type("get_semester_context", {}) == QueryType.EXPLANATION
        assert classify_query_type("unknown_tool", {}) == QueryType.UNKNOWN


class TestDetectMetaSkills:
    """Tests for meta-skill detection."""

    def test_verification_attempted(self) -> None:
        """Should detect verification attempts."""
        indicators = detect_meta_skills("I tried running the tests but they fail")
        assert indicators.verification_attempted is True

        indicators = detect_meta_skills("I tested this locally")
        assert indicators.verification_attempted is True

    def test_test_run_before_query(self) -> None:
        """Should detect test-related queries."""
        indicators = detect_meta_skills("The test failed with this error")
        assert indicators.test_run_before_query is True

        indicators = detect_meta_skills("pytest shows a traceback")
        assert indicators.test_run_before_query is True

    def test_references_existing_code(self) -> None:
        """Should detect code references."""
        indicators = detect_meta_skills("In the file utils.py there's a problem")
        assert indicators.references_existing_code is True

        indicators = detect_meta_skills("The function parse_data is broken")
        assert indicators.references_existing_code is True

    def test_hypothesis_present(self) -> None:
        """Should detect hypotheses."""
        indicators = detect_meta_skills("I think the problem is in the cache")
        assert indicators.hypothesis_present is True

        indicators = detect_meta_skills("Maybe because the token expired")
        assert indicators.hypothesis_present is True

        indicators = detect_meta_skills("Could it be a race condition?")
        assert indicators.hypothesis_present is True

    def test_architectural_awareness(self) -> None:
        """Should detect architectural understanding."""
        indicators = detect_meta_skills("How does this fit into the architecture?")
        assert indicators.architectural_awareness is True

        indicators = detect_meta_skills("What pattern should I use here?")
        assert indicators.architectural_awareness is True

    def test_error_quality_diagnostic(self) -> None:
        """Should detect diagnostic error descriptions."""
        indicators = detect_meta_skills(
            "The error occurs because when I call the API then it returns null"
        )
        assert indicators.error_description_quality == "diagnostic"

    def test_error_quality_specific(self) -> None:
        """Should detect specific error descriptions."""
        indicators = detect_meta_skills("Error on line 42, expected int got string")
        assert indicators.error_description_quality == "specific"

    def test_error_quality_vague(self) -> None:
        """Should detect vague error descriptions."""
        indicators = detect_meta_skills("It doesn't work")
        assert indicators.error_description_quality == "vague"

        indicators = detect_meta_skills("Something is wrong with the code")
        assert indicators.error_description_quality == "vague"

    def test_error_quality_none(self) -> None:
        """Should return 'none' for non-error queries."""
        indicators = detect_meta_skills("How do I implement sorting?")
        assert indicators.error_description_quality == "none"

    def test_empty_query(self) -> None:
        """Should handle empty or None queries."""
        indicators = detect_meta_skills(None)
        assert indicators.verification_attempted is False
        assert indicators.hypothesis_present is False

        indicators = detect_meta_skills("")
        assert indicators.verification_attempted is False


class TestExtractResultCount:
    """Tests for result count extraction."""

    def test_h2_headers(self) -> None:
        """Should count H2 headers."""
        response = """
# Main Title

## Result 1
Content

## Result 2
Content

## Result 3
Content
"""
        assert extract_result_count(response) == 3

    def test_h3_headers(self) -> None:
        """Should count H3 headers if no H2."""
        response = """
### Item 1
Content

### Item 2
Content
"""
        assert extract_result_count(response) == 2

    def test_numbered_list(self) -> None:
        """Should count numbered list items."""
        response = """
1. First item
2. Second item
3. Third item
4. Fourth item
"""
        assert extract_result_count(response) == 4

    def test_bullet_points(self) -> None:
        """Should count bullet points."""
        response = """
- Item one
- Item two
- Item three
"""
        assert extract_result_count(response) == 3

    def test_empty_response(self) -> None:
        """Should handle empty response."""
        assert extract_result_count("") == 0
        assert extract_result_count("Just some text") is None
