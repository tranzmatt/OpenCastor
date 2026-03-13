from castor.providers.task_router import TaskCategory, TaskRouter


class TestTaskRouter:
    def test_selects_preferred_provider(self):
        r = TaskRouter()
        result = r.select(TaskCategory.CODE, ["anthropic", "deepseek", "ollama"])
        assert result == "deepseek"  # preferred for CODE

    def test_falls_back_when_preferred_unavailable(self):
        r = TaskRouter()
        result = r.select(TaskCategory.CODE, ["anthropic"])
        assert result == "anthropic"

    def test_returns_none_when_no_providers(self):
        r = TaskRouter()
        assert r.select(TaskCategory.REASONING, []) is None

    def test_safety_never_uses_cheap(self):
        r = TaskRouter()
        result = r.select(TaskCategory.SAFETY, ["ollama", "anthropic"])
        assert result == "anthropic"

    def test_string_category(self):
        r = TaskRouter()
        result = r.select("code", ["deepseek"])
        assert result == "deepseek"

    def test_unknown_category_falls_back_to_reasoning(self):
        r = TaskRouter()
        result = r.select("nonsense", ["anthropic"])
        assert result == "anthropic"

    def test_custom_routing_table(self):
        r = TaskRouter(routing_table={"sensor_poll": ["custom_provider"]})
        result = r.select(TaskCategory.SENSOR_POLL, ["custom_provider", "anthropic"])
        assert result == "custom_provider"

    def test_update(self):
        r = TaskRouter()
        r.update("vision", ["custom_vision"])
        assert r.select(TaskCategory.VISION, ["custom_vision"]) == "custom_vision"

    def test_openrouter_reachable_when_preferred_unavailable(self):
        """openrouter should be reachable as a fallback for all task categories."""
        r = TaskRouter()
        for category in TaskCategory:
            result = r.select(category, ["openrouter"])
            assert result == "openrouter", (
                f"openrouter not reachable for {category.value} — missing from _DEFAULT_ROUTING"
            )

    def test_openrouter_not_preferred_over_local_for_sensor_poll(self):
        """Local providers (ollama) should beat openrouter for cheap SENSOR_POLL tasks."""
        r = TaskRouter()
        result = r.select(TaskCategory.SENSOR_POLL, ["ollama", "openrouter"])
        assert result == "ollama"

    def test_openrouter_used_when_primary_providers_absent(self):
        """openrouter is a cloud fallback for REASONING when anthropic/openai/gemini are absent."""
        r = TaskRouter()
        result = r.select(TaskCategory.REASONING, ["openrouter", "ollama"])
        assert result == "openrouter"
