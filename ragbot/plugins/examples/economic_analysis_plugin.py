"""
Economic Analysis Plugin

This plugin provides economic data analysis, financial metrics calculation,
and market trends analysis capabilities for economic reports.
"""

from typing import Dict, Any, Optional, List
import asyncio
import json
import re
from datetime import datetime, timedelta
from statistics import mean, median, stdev

from ragbot.plugins.base_plugin import (
    BasePlugin,
    PluginContext,
    PluginResult,
    PluginType,
    PluginStatus,
    HookType,
)
from ragbot.outputs.logger import logger


class EconomicAnalysisPlugin(BasePlugin):
    """
    Economic Analysis Plugin for financial data processing

    Provides:
    - Economic indicators extraction
    - Financial ratios calculation
    - Market trend analysis
    - Inflation rate analysis
    - GDP growth calculations
    - Exchange rate correlations
    """

    def __init__(self, plugin_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(plugin_id, config)

        # Default configuration
        self.default_config = {
            "supported_currencies": ["USD", "EUR", "IRR", "GBP", "JPY"],
            "economic_indicators": ["GDP", "CPI", "Unemployment", "Interest_Rate"],
            "analysis_periods": ["daily", "weekly", "monthly", "quarterly", "yearly"],
            "confidence_levels": [0.95, 0.99],
            "trend_threshold": 0.05,  # 5% threshold for significant trends
            "auto_analyze_patterns": True,
            "extract_financial_data": True,
            "calculate_ratios": True,
            "generate_predictions": True,
            "historical_depth_months": 12,
        }

        # Merge with provided config
        self.config.update(self.default_config)

        # Data storage for analysis
        self.economic_data: Dict[str, List[float]] = {}
        self.financial_metrics: Dict[str, Dict[str, Any]] = {}
        self.trend_analysis: Dict[str, Dict[str, Any]] = {}

    @property
    def plugin_name(self) -> str:
        return "Economic Analysis Plugin"

    @property
    def plugin_version(self) -> str:
        return "1.0.0"

    @property
    def plugin_description(self) -> str:
        return (
            "Advanced economic analysis plugin providing financial metrics calculation, "
            "market trend analysis, and economic indicator processing"
        )

    @property
    def plugin_type(self) -> PluginType:
        return PluginType.DATA_PROCESSOR

    @property
    def plugin_author(self) -> str:
        return "RAG Bot Economic Team"

    async def initialize(self, context: PluginContext) -> bool:
        """Initialize the plugin"""
        try:
            logger.info("Initializing Economic Analysis Plugin...")

            # Initialize economic data structures
            for indicator in self.config["economic_indicators"]:
                self.economic_data[indicator] = []
                self.trend_analysis[indicator] = {}

            # Register hooks for automatic analysis
            if self.config.get("auto_analyze_patterns", True):
                self.register_hook(
                    HookType.POST_DOCUMENT_INGEST, self._analyze_document_content
                )
                self.register_hook(HookType.POST_QUERY, self._analyze_query_context)

            logger.info("Economic Analysis Plugin initialized successfully")
            self.set_status(PluginStatus.ACTIVE)
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Economic Analysis Plugin: {e}")
            self.set_status(PluginStatus.REQUESTED)
            return False

    async def execute(self, context: PluginContext) -> PluginResult:
        """Execute main economic analysis functionality"""
        try:
            start_time = asyncio.get_event_loop().time()

            # Get analysis type and data from context
            analysis_type = (
                context.data.get("analysis_type", "comprehensive")
                if context.data
                else "comprehensive"
            )
            data = context.data.get("data", "") if context.data else ""
            text_content = context.data.get("text", "") if context.data else ""

            results = {}

            if analysis_type == "financial_extraction":
                results = await self._extract_financial_data(data or text_content)
            elif analysis_type == "trend_analysis":
                results = await self._analyze_trends(data or text_content)
            elif analysis_type == "ratio_calculation":
                results = await self._calculate_financial_ratios(data or text_content)
            elif analysis_type == "prediction":
                results = await self._generate_predictions(data or text_content)
            else:  # comprehensive
                results = await self._comprehensive_analysis(data or text_content)

            execution_time = asyncio.get_event_loop().time() - start_time

            return PluginResult(
                success=True,
                data=results,
                metadata={
                    "plugin_id": self.plugin_id,
                    "analysis_type": analysis_type,
                    "execution_time": execution_time,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        except Exception as e:
            logger.error(f"Economic analysis execution error: {e}")
            return PluginResult(
                success=False, error_message=f"Economic analysis error: {str(e)}"
            )

    async def cleanup(self) -> bool:
        """Cleanup plugin resources"""
        try:
            logger.info("Cleaning up Economic Analysis Plugin...")

            # Clear accumulated data
            self.economic_data.clear()
            self.financial_metrics.clear()
            self.trend_analysis.clear()

            logger.info("Economic Analysis Plugin cleanup completed")
            return True

        except Exception as e:
            logger.error(f"Plugin cleanup error: {e}")
            return False

    async def _extract_financial_data(self, text: str) -> Dict[str, Any]:
        """Extract financial data from text"""
        try:
            extracted_data = {
                "currencies": [],
                "percentages": [],
                "numbers": [],
                "dates": [],
                "indicators": {},
                "financial_terms": [],
            }

            # Extract currencies
            currency_pattern = r"(\d+(?:\.\d+)?)\s*(USD|EUR|IRR|GBP|JPY|تومان|ریال)"
            currencies = re.findall(currency_pattern, text, re.IGNORECASE)
            extracted_data["currencies"] = currencies

            # Extract percentages
            percentage_pattern = r"(\d+(?:\.\d+)?)\s*%"
            percentages = re.findall(percentage_pattern, text)
            extracted_data["percentages"] = percentages

            # Extract large numbers (potential economic indicators)
            number_pattern = r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)"
            numbers = re.findall(number_pattern, text)
            extracted_data["numbers"] = numbers

            # Extract economic indicators
            for indicator in self.config["economic_indicators"]:
                pattern = f"{indicator}[:\s]+(\d+(?:\.\d+)?)"
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    extracted_data["indicators"][indicator] = matches

            # Extract financial terms
            financial_terms = [
                "رشد",
                "تورم",
                "GDP",
                "CPI",
                "Unemployment",
                "Finance",
                "اقتصاد",
                "بازار",
                "سرمایه",
                "سرمایه‌گذاری",
                "قیمت",
            ]

            for term in financial_terms:
                if term.lower() in text.lower():
                    extracted_data["financial_terms"].append(term)

            logger.info(
                f"Extracted financial data from text: {len(extracted_data['currencies'])} currencies, "
                f"{len(extracted_data['percentages'])} percentages"
            )

            return extracted_data

        except Exception as e:
            logger.error(f"Financial data extraction error: {e}")
            return {"error": str(e)}

    async def _analyze_trends(self, data: str) -> Dict[str, Any]:
        """Analyze economic trends"""
        try:
            trends = {
                "growth_patterns": {},
                "volatility_analysis": {},
                "correlation_matrix": {},
                "seasonality": {},
                "market_sentiment": "neutral",
            }

            # Extract numeric data for analysis
            numbers = re.findall(r"(\d+(?:\.\d+)?)", data)
            numeric_values = [float(n) for n in numbers]

            if len(numeric_values) >= 3:
                # Calculate basic trends
                trends["growth_patterns"] = {
                    "mean_growth": mean(numeric_values),
                    "median_growth": median(numeric_values),
                    "volatility": stdev(numeric_values)
                    if len(numeric_values) > 1
                    else 0,
                    "min_value": min(numeric_values),
                    "max_value": max(numeric_values),
                }

                # Detect trend direction
                if len(numeric_values) >= 5:
                    recent_avg = mean(numeric_values[-3:])
                    historical_avg = mean(numeric_values[:-3])

                    if recent_avg > historical_avg * 1.05:
                        trends["market_sentiment"] = "bullish"
                    elif recent_avg < historical_avg * 0.95:
                        trends["market_sentiment"] = "bearish"

            logger.info(
                f"Trend analysis completed: sentiment = {trends['market_sentiment']}"
            )
            return trends

        except Exception as e:
            logger.error(f"Trend analysis error: {e}")
            return {"error": str(e)}

    async def _calculate_financial_ratios(self, data: str) -> Dict[str, Any]:
        """Calculate financial ratios"""
        try:
            ratios = {
                "profit_margin": [],
                "debt_to_equity": [],
                "return_on_investment": [],
                "liquidity_ratios": [],
                "efficiency_ratios": [],
            }

            # Extract financial values
            numbers = re.findall(r"(\d+(?:\.\d+)?)", data)
            numeric_values = [float(n) for n in numbers]

            if len(numeric_values) >= 2:
                # Calculate basic ratios
                for i in range(len(numeric_values) - 1):
                    current = numeric_values[i]
                    next_val = numeric_values[i + 1]

                    if next_val != 0:
                        ratio = current / next_val

                        # Categorize ratios based on typical financial ranges
                        if 0.01 <= ratio <= 2.0:
                            ratios["profit_margin"].append(ratio)
                        elif 0.1 <= ratio <= 10.0:
                            ratios["debt_to_equity"].append(ratio)
                        elif 0.01 <= ratio <= 0.5:
                            ratios["return_on_investment"].append(ratio)

            logger.info(f"Financial ratios calculated: {len(numbers)} values processed")
            return ratios

        except Exception as e:
            logger.error(f"Financial ratio calculation error: {e}")
            return {"error": str(e)}

    async def _generate_predictions(self, data: str) -> Dict[str, Any]:
        """Generate economic predictions"""
        try:
            predictions = {
                "short_term_forecast": {},
                "long_term_projection": {},
                "risk_assessment": {},
                "confidence_scores": {},
            }

            # Extract historical data for prediction
            numbers = re.findall(r"(\d+(?:\.\d+)?)", data)
            numeric_values = [float(n) for n in numbers]

            if len(numeric_values) >= 5:
                # Simple linear trend for prediction
                recent_values = numeric_values[-5:]

                # Calculate trend
                trend = []
                for i in range(1, len(recent_values)):
                    trend.append(recent_values[i] - recent_values[i - 1])

                avg_trend = mean(trend) if trend else 0

                # Generate predictions
                last_value = recent_values[-1]

                predictions["short_term_forecast"] = {
                    "next_period": last_value + avg_trend,
                    "confidence": min(0.95, len(recent_values) / 10),
                    "trend_direction": "positive" if avg_trend > 0 else "negative",
                }

                predictions["long_term_projection"] = {
                    "next_3_periods": last_value + (avg_trend * 3),
                    "confidence": min(0.80, len(recent_values) / 20),
                    "risk_level": "medium",
                }

            logger.info("Economic predictions generated successfully")
            return predictions

        except Exception as e:
            logger.error(f"Prediction generation error: {e}")
            return {"error": str(e)}

    async def _comprehensive_analysis(self, data: str) -> Dict[str, Any]:
        """Perform comprehensive economic analysis"""
        try:
            comprehensive_results = {
                "data_extraction": await self._extract_financial_data(data),
                "trend_analysis": await self._analyze_trends(data),
                "financial_ratios": await self._calculate_financial_ratios(data),
                "predictions": await self._generate_predictions(data),
                "overall_assessment": {},
            }

            # Generate overall assessment
            trend_data = comprehensive_results["trend_analysis"]
            financial_data = comprehensive_results["financial_ratios"]

            assessment = {
                "economic_health": "good",
                "risk_level": "medium",
                "growth_outlook": "positive",
                "recommendation": "monitor",
            }

            # Determine assessment based on available data
            if "market_sentiment" in trend_data:
                sentiment = trend_data["market_sentiment"]
                if sentiment == "bullish":
                    assessment["economic_health"] = "excellent"
                    assessment["growth_outlook"] = "very_positive"
                elif sentiment == "bearish":
                    assessment["economic_health"] = "poor"
                    assessment["risk_level"] = "high"

            comprehensive_results["overall_assessment"] = assessment

            logger.info(
                f"Comprehensive analysis completed: health = {assessment['economic_health']}"
            )
            return comprehensive_results

        except Exception as e:
            logger.error(f"Comprehensive analysis error: {e}")
            return {"error": str(e)}

    async def _analyze_document_content(
        self, context: PluginContext
    ) -> List[PluginResult]:
        """Hook: Analyze document for economic data during ingestion"""
        try:
            content = context.data.get("content", "") if context.data else ""
            if not content or len(content) < 100:
                return [PluginResult(success=True)]

            # Extract economic data
            extracted_data = await self._extract_financial_data(content)

            return [
                PluginResult(
                    success=True,
                    data={
                        "document_economic_data": extracted_data,
                        "has_financial_content": len(extracted_data["financial_terms"])
                        > 0,
                        "analysis_timestamp": datetime.now().isoformat(),
                    },
                )
            ]

        except Exception as e:
            logger.error(f"Document analysis hook error: {e}")
            return [PluginResult(success=False, error_message=str(e))]

    async def _analyze_query_context(
        self, context: PluginContext
    ) -> List[PluginResult]:
        """Hook: Analyze query context for economic intent"""
        try:
            query = context.data.get("query", "") if context.data else ""
            if not query:
                return [PluginResult(success=True)]

            # Detect economic query intent
            economic_keywords = [
                "اقتصاد",
                "financial",
                "اقتصادی",
                "بازار",
                "market",
                "سرمایه",
                "investment",
                "قیمت",
                "price",
                "رشد",
                "growth",
                "تورم",
                "inflation",
            ]

            has_economic_intent = any(
                keyword.lower() in query.lower() for keyword in economic_keywords
            )

            if has_economic_intent:
                extracted_data = await self._extract_financial_data(query)

                return [
                    PluginResult(
                        success=True,
                        data={
                            "economic_query_detected": True,
                            "extracted_intent_data": extracted_data,
                            "query_analysis_timestamp": datetime.now().isoformat(),
                        },
                    )
                ]

            return [PluginResult(success=True, data={"economic_query_detected": False})]

        except Exception as e:
            logger.error(f"Query context analysis error: {e}")
            return [PluginResult(success=False, error_message=str(e))]

    def get_economic_stats(self) -> Dict[str, Any]:
        """Get economic analysis statistics"""
        return {
            "supported_currencies": self.config["supported_currencies"],
            "economic_indicators": self.config["economic_indicators"],
            "historical_data_points": sum(
                len(data) for data in self.economic_data.values()
            ),
            "trend_analyses_completed": len(self.trend_analysis),
            "financial_metrics_calculated": len(self.financial_metrics),
            "auto_analysis_enabled": self.config.get("auto_analyze_patterns", True),
        }
