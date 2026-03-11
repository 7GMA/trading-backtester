"""Tests for the offline strategy parser."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.strategy.parser import parse_strategy_offline
from src.strategy.models import Operator


class TestRSIParsing:
    """Test RSI pattern detection in various inputs."""

    def test_rsi_english_basic(self):
        result = parse_strategy_offline("Buy when RSI below 30 on AAPL")
        assert result is not None
        strategy, warnings = result
        assert strategy.asset == "AAPL"
        assert len(strategy.entry.conditions) == 1
        cond = strategy.entry.conditions[0]
        assert cond.indicator == "RSI"
        assert cond.operator == Operator.LT
        assert cond.value == 30

    def test_rsi_german_unter(self):
        result = parse_strategy_offline("Kaufe wenn RSI unter 25 bei TSLA")
        assert result is not None
        strategy, warnings = result
        assert strategy.asset == "TSLA"
        cond = strategy.entry.conditions[0]
        assert cond.value == 25

    def test_rsi_with_less_than_symbol(self):
        result = parse_strategy_offline("Buy MSFT when RSI < 35")
        assert result is not None
        strategy, warnings = result
        assert strategy.asset == "MSFT"
        cond = strategy.entry.conditions[0]
        assert cond.value == 35

    def test_rsi_default_exit_values(self):
        result = parse_strategy_offline("RSI below 30 on AAPL")
        assert result is not None
        strategy, _ = result
        assert strategy.exit.stop_loss == 0.05
        assert strategy.exit.take_profit == 0.10

    def test_rsi_german_faellt_unter(self):
        result = parse_strategy_offline("Kaufe wenn RSI fällt unter 30")
        assert result is not None
        strategy, _ = result
        cond = strategy.entry.conditions[0]
        assert cond.indicator == "RSI"
        assert cond.value == 30


class TestGoldenCrossParsing:
    """Test Golden Cross / SMA crossover detection."""

    def test_golden_cross_english(self):
        result = parse_strategy_offline("Use golden cross strategy on SPY")
        assert result is not None
        strategy, warnings = result
        assert strategy.asset == "SPY"
        cond = strategy.entry.conditions[0]
        assert cond.indicator == "SMA"
        assert cond.operator == Operator.CROSS_ABOVE

    def test_sma_cross_english(self):
        result = parse_strategy_offline("SMA crossover strategy for AAPL")
        assert result is not None
        strategy, _ = result
        cond = strategy.entry.conditions[0]
        assert cond.indicator == "SMA"
        assert cond.operator == Operator.CROSS_ABOVE

    def test_golden_cross_has_exit_conditions(self):
        result = parse_strategy_offline("Golden cross on SPY")
        assert result is not None
        strategy, _ = result
        assert len(strategy.exit.conditions) > 0
        exit_cond = strategy.exit.conditions[0]
        assert exit_cond.operator == Operator.CROSS_BELOW


class TestMACDParsing:
    """Test MACD crossover detection."""

    def test_macd_crossover_english(self):
        result = parse_strategy_offline("MACD crossover on AAPL")
        assert result is not None
        strategy, warnings = result
        cond = strategy.entry.conditions[0]
        assert cond.indicator == "MACD"
        assert cond.operator == Operator.CROSS_ABOVE

    def test_macd_cross_english(self):
        result = parse_strategy_offline("Buy when MACD crosses signal on NVDA")
        assert result is not None
        strategy, _ = result
        assert strategy.asset == "NVDA"
        cond = strategy.entry.conditions[0]
        assert cond.indicator == "MACD"

    def test_macd_german_kreuzt(self):
        result = parse_strategy_offline("MACD kreuzt Signal für TSLA")
        assert result is not None
        strategy, _ = result
        assert strategy.asset == "TSLA"
        cond = strategy.entry.conditions[0]
        assert cond.indicator == "MACD"

    def test_macd_has_exit_conditions(self):
        result = parse_strategy_offline("MACD crossover on AAPL")
        assert result is not None
        strategy, _ = result
        assert len(strategy.exit.conditions) > 0
        exit_cond = strategy.exit.conditions[0]
        assert exit_cond.operator == Operator.CROSS_BELOW


class TestAssetDetection:
    """Test asset/ticker recognition from natural language."""

    def test_explicit_ticker(self):
        result = parse_strategy_offline("RSI below 30 on GOOGL")
        assert result is not None
        strategy, _ = result
        assert strategy.asset == "GOOGL"

    def test_alias_apple(self):
        result = parse_strategy_offline("golden cross strategy for apple")
        assert result is not None
        strategy, _ = result
        assert strategy.asset == "AAPL"

    def test_alias_bitcoin(self):
        result = parse_strategy_offline("RSI below 25 for bitcoin")
        assert result is not None
        strategy, _ = result
        assert strategy.asset == "BTC-USD"

    def test_alias_tesla(self):
        result = parse_strategy_offline("MACD crossover for tesla")
        assert result is not None
        strategy, _ = result
        assert strategy.asset == "TSLA"

    def test_alias_nvidia(self):
        result = parse_strategy_offline("RSI below 30 for nvidia")
        assert result is not None
        strategy, _ = result
        assert strategy.asset == "NVDA"


class TestStopLossTakeProfit:
    """Test stop loss and take profit parsing."""

    def test_custom_stop_loss(self):
        result = parse_strategy_offline("RSI below 30 on AAPL with 10% stop loss")
        assert result is not None
        strategy, _ = result
        assert strategy.exit.stop_loss == 0.10

    def test_custom_take_profit(self):
        result = parse_strategy_offline("RSI below 30 on AAPL with 20% take profit")
        assert result is not None
        strategy, _ = result
        assert strategy.exit.take_profit == 0.20

    def test_defaults_when_not_specified(self):
        result = parse_strategy_offline("RSI below 30 on AAPL")
        assert result is not None
        strategy, _ = result
        assert strategy.exit.stop_loss == 0.05
        assert strategy.exit.take_profit == 0.10


class TestUnrecognizedInput:
    """Test that unrecognized inputs return None."""

    def test_gibberish(self):
        result = parse_strategy_offline("hello world how are you")
        assert result is None

    def test_empty_string(self):
        result = parse_strategy_offline("")
        assert result is None

    def test_no_strategy_keywords(self):
        result = parse_strategy_offline("I like pizza and sunshine")
        assert result is None


class TestValidation:
    """Test that parsed strategies pass validation."""

    def test_rsi_no_warnings(self):
        result = parse_strategy_offline("RSI below 30 on AAPL")
        assert result is not None
        _, warnings = result
        assert len(warnings) == 0

    def test_golden_cross_no_warnings(self):
        result = parse_strategy_offline("Golden cross on SPY")
        assert result is not None
        _, warnings = result
        assert len(warnings) == 0

    def test_macd_no_warnings(self):
        result = parse_strategy_offline("MACD crossover on AAPL")
        assert result is not None
        _, warnings = result
        assert len(warnings) == 0
