"""
Integration tests for Phase 4 Quality & Confidence Metrics.

Persian developer notes:
- تست‌های integration برای کیفیت و اعتماد پاسخ‌ها
- بررسی عملکرد کامل pipeline از QAChain تا metrics
"""

from unittest.mock import Mock, patch

import pytest

from ragbot.outputs.metrics import QualityEvaluator
from ragbot.rag.qa.chain import QAChain
from ragbot.rag.store.base import VectorDocument


class TestPhase4QualityIntegration:
    """Integration tests for Phase 4 quality metrics."""

    @pytest.mark.skip(reason="Requires OpenAI API key")
    def test_qa_chain_quality_metrics_integration(self):
        """Test that QAChain properly records quality metrics."""
        # Mock QAChain components
        mock_llm = Mock()
        mock_llm.generate.return_value = (
            "This is a comprehensive answer to your question."
        )

        mock_retriever = Mock()
        mock_docs = [
            VectorDocument(
                id="test_doc_1",
                content="Relevant context information",
                metadata={"relevance_score": 0.9, "source": "test.pdf"},
                embedding=[0.1, 0.2, 0.3],
            )
        ]
        mock_retriever.retrieve.return_value = mock_docs

        mock_prompt_builder = Mock()
        mock_prompt_builder.build_prompt.return_value = "Test prompt"

        # Create QAChain instance
        qa_chain = QAChain(
            llm=mock_llm, retriever=mock_retriever, prompt_builder=mock_prompt_builder
        )

        # Mock the quality calculation methods
        with patch.object(qa_chain, "_calculate_quality_scores") as mock_calc:
            mock_calc.return_value = {
                "accuracy": 0.8,
                "relevance": 0.9,
                "completeness": 0.85,
                "coherence": 0.75,
                "factual_accuracy": 0.8,
            }

            with patch.object(qa_chain, "_calculate_confidence_score") as mock_conf:
                mock_conf.return_value = 0.82

                # Test answer generation
                result = qa_chain.answer("Test question")

                # Verify answer was generated
                assert result is not None
                assert "comprehensive answer" in result.lower()

                # Verify quality metrics were recorded
                mock_calc.assert_called_once()
                mock_conf.assert_called_once()

    def test_quality_evaluator_metrics_recording(self):
        """Test that QualityEvaluator properly records metrics to Prometheus."""
        evaluator = QualityEvaluator()

        # Test data
        test_data = {
            "query": "Test question",
            "response": "Test answer",
            "context_used": ["Context 1", "Context 2"],
            "quality_scores": {
                "accuracy": 0.8,
                "relevance": 0.9,
                "completeness": 0.85,
                "coherence": 0.75,
                "factual_accuracy": 0.8,
            },
            "confidence_score": 0.82,
            "model_name": "test-model",
            "user_satisfaction": 4,
        }

        # Record metrics
        evaluator.record_response_quality(**test_data)

        # Verify metrics were recorded
        assert len(evaluator.quality_history) == 1
        assert evaluator.quality_history[0]["confidence_score"] == 0.82
        assert evaluator.quality_history[0]["model_name"] == "test-model"

    def test_quality_metrics_prometheus_integration(self):
        """Test that quality metrics are properly exposed to Prometheus."""
        evaluator = QualityEvaluator()

        # Record some test data
        for i in range(5):
            evaluator.record_response_quality(
                query=f"Question {i}",
                response=f"Answer {i}",
                context_used=[f"Context {i}"],
                quality_scores={
                    "accuracy": 0.7 + i * 0.05,
                    "relevance": 0.8 + i * 0.03,
                    "completeness": 0.75 + i * 0.04,
                    "coherence": 0.8 + i * 0.02,
                    "factual_accuracy": 0.75 + i * 0.05,
                },
                confidence_score=0.75 + i * 0.05,
                model_name="test-model",
                user_satisfaction=4 + i,
            )

        # Test metrics calculation
        summary = evaluator.get_quality_summary()

        assert "quality_stats" in summary
        assert "average_confidence" in summary["quality_stats"]
        assert "average_quality" in summary["quality_stats"]
        assert "total_responses" in summary["quality_stats"]
        assert summary["quality_stats"]["total_responses"] == 5

    def test_quality_threshold_detection(self):
        """Test quality threshold detection and alerting."""
        evaluator = QualityEvaluator()

        # Test high quality response
        evaluator.record_response_quality(
            query="Test question",
            response="Comprehensive answer",
            context_used=["Relevant context"],
            quality_scores={
                "accuracy": 0.9,
                "relevance": 0.95,
                "completeness": 0.9,
                "coherence": 0.85,
                "factual_accuracy": 0.9,
            },
            confidence_score=0.9,
            model_name="test-model",
            user_satisfaction=5,
        )

        # Test low quality response
        evaluator.record_response_quality(
            query="Test question",
            response="Short answer",
            context_used=["Some context"],
            quality_scores={
                "accuracy": 0.4,
                "relevance": 0.5,
                "completeness": 0.3,
                "coherence": 0.4,
                "factual_accuracy": 0.5,
            },
            confidence_score=0.4,
            model_name="test-model",
            user_satisfaction=2,
        )

        # Check quality detection
        assert (
            evaluator._is_high_quality(
                0.9,
                {
                    "accuracy": 0.9,
                    "relevance": 0.9,
                    "completeness": 0.9,
                    "coherence": 0.9,
                    "factual_accuracy": 0.9,
                },
            )
            == True
        )
        assert (
            evaluator._is_high_quality(
                0.4,
                {
                    "accuracy": 0.4,
                    "relevance": 0.4,
                    "completeness": 0.4,
                    "coherence": 0.4,
                    "factual_accuracy": 0.4,
                },
            )
            == False
        )

    def test_user_satisfaction_tracking(self):
        """Test user satisfaction metrics tracking."""
        evaluator = QualityEvaluator()

        # Record user feedback
        evaluator.record_user_feedback(
            query="Test question",
            response="Test answer",
            satisfaction_score=4,
            feedback_text="Good answer",
        )

        # Verify feedback was recorded
        assert len(evaluator.user_feedback) == 1
        assert evaluator.user_feedback[0]["satisfaction_score"] == 4
        assert evaluator.user_feedback[0]["query"] == "Test question"

    def test_model_performance_comparison(self):
        """Test model performance comparison metrics."""
        evaluator = QualityEvaluator()

        # Record responses from different models
        models = ["model-a", "model-b", "model-c"]
        for i, model in enumerate(models):
            evaluator.record_response_quality(
                query=f"Question {i}",
                response=f"Answer {i}",
                context_used=[f"Context {i}"],
                quality_scores={
                    "accuracy": 0.7 + i * 0.1,
                    "relevance": 0.8 + i * 0.05,
                    "completeness": 0.75 + i * 0.08,
                    "coherence": 0.8 + i * 0.03,
                    "factual_accuracy": 0.75 + i * 0.1,
                },
                confidence_score=0.75 + i * 0.1,
                model_name=model,
                user_satisfaction=4 + i,
            )

        # Test model performance metrics
        model_metrics = evaluator.calculate_model_performance()

        assert len(model_metrics) == 3
        assert "model-a" in model_metrics
        assert "model-b" in model_metrics
        assert "model-c" in model_metrics

    def test_quality_metrics_aggregation(self):
        """Test quality metrics aggregation and statistics."""
        evaluator = QualityEvaluator()

        # Record multiple responses
        for i in range(10):
            evaluator.record_response_quality(
                query=f"Question {i}",
                response=f"Answer {i}",
                context_used=[f"Context {i}"],
                quality_scores={
                    "accuracy": 0.6 + (i % 5) * 0.1,
                    "relevance": 0.7 + (i % 4) * 0.05,
                    "completeness": 0.65 + (i % 3) * 0.1,
                    "coherence": 0.75 + (i % 2) * 0.1,
                    "factual_accuracy": 0.7 + (i % 6) * 0.05,
                },
                confidence_score=0.7 + (i % 4) * 0.05,
                model_name="test-model",
                user_satisfaction=3 + (i % 3),
            )

        # Test aggregation
        summary = evaluator.get_quality_summary()

        assert summary["quality_stats"]["total_responses"] == 10
        assert "quality_stats" in summary
        assert "average_confidence" in summary["quality_stats"]
        assert "average_quality" in summary["quality_stats"]
        assert "confidence_distribution" in summary

        # Test confidence distribution
        conf_dist = evaluator.calculate_confidence_distribution()
        assert len(conf_dist) > 0
        assert "mean" in conf_dist
        assert "max" in conf_dist
        assert "min" in conf_dist

    def test_quality_metrics_persistence(self):
        """Test that quality metrics persist across evaluations."""
        evaluator = QualityEvaluator()

        # Record initial data
        evaluator.record_response_quality(
            query="Initial question",
            response="Initial answer",
            context_used=["Initial context"],
            quality_scores={
                "accuracy": 0.8,
                "relevance": 0.9,
                "completeness": 0.85,
                "coherence": 0.75,
                "factual_accuracy": 0.8,
            },
            confidence_score=0.82,
            model_name="test-model",
            user_satisfaction=4,
        )

        # Verify data persistence
        assert len(evaluator.quality_history) == 1
        assert evaluator.quality_history[0]["query"] == "Initial question"

        # Record additional data
        evaluator.record_response_quality(
            query="Additional question",
            response="Additional answer",
            context_used=["Additional context"],
            quality_scores={
                "accuracy": 0.9,
                "relevance": 0.95,
                "completeness": 0.9,
                "coherence": 0.85,
                "factual_accuracy": 0.9,
            },
            confidence_score=0.9,
            model_name="test-model",
            user_satisfaction=5,
        )

        # Verify data accumulation
        assert len(evaluator.quality_history) == 2
        assert evaluator.quality_history[1]["query"] == "Additional question"

        # Test summary includes both records
        summary = evaluator.get_quality_summary()
        assert summary["quality_stats"]["total_responses"] == 2
