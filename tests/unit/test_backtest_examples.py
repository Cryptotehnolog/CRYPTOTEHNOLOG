# ==================== Tests for backtest/examples.py ====================


from cryptotechnolog.backtest import examples


class TestBacktestExamples:
    """Tests for backtest examples module."""

    def test_example_simple_runs(self):
        """Test example_simple executes without error."""
        result = examples.example_simple()

        assert isinstance(result, dict)
        assert "ticks_processed" in result
        assert "final_balance" in result
        assert result["ticks_processed"] == 100

    def test_example_simple_returns_correct_keys(self):
        """Test example_simple returns expected keys."""
        result = examples.example_simple()

        # These keys are confirmed in the output
        expected_keys = [
            "ticks_processed",
            "final_balance",
        ]

        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_example_simple_balance_stays_same(self):
        """Test simple example with no trades keeps balance."""
        result = examples.example_simple()

        # With no trades, balance should equal initial
        assert result["final_balance"] == 10000.0

    def test_example_with_callbacks_runs(self):
        """Test example_with_callbacks executes without error."""
        result = examples.example_with_callbacks()

        assert isinstance(result, dict)
        assert "ticks_processed" in result
        assert result["ticks_processed"] == 1000

    def test_example_with_callbacks_returns_dict(self):
        """Test example_with_callbacks returns expected format."""
        result = examples.example_with_callbacks()

        assert isinstance(result, dict)
        assert "final_balance" in result
        assert isinstance(result["final_balance"], float)

    def test_example_conditional_runs(self):
        """Test example_conditional executes without error."""
        result = examples.example_conditional()

        assert isinstance(result, dict)
        assert "ticks_processed" in result
        assert "final_balance" in result

    def test_example_conditional_has_max_ticks(self):
        """Test conditional example respects max_ticks."""
        result = examples.example_conditional()

        # Should stop at max_ticks=5000 or less
        assert result["ticks_processed"] <= 5000

    def test_example_conditional_declining_price(self):
        """Test conditional example with declining price."""
        result = examples.example_conditional()

        # With declining price, balance should decrease
        # (but not below threshold due to stop condition)
        assert result["final_balance"] >= 9000.0

    def test_examples_module_imports(self):
        """Test backtest.examples module imports correctly."""
        assert hasattr(examples, "example_simple")
        assert hasattr(examples, "example_with_callbacks")
        assert hasattr(examples, "example_conditional")

    def test_example_functions_are_callable(self):
        """Test all example functions are callable."""
        assert callable(examples.example_simple)
        assert callable(examples.example_with_callbacks)
        assert callable(examples.example_conditional)
