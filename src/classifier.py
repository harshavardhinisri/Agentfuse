"""DeBERTa classifier for action safety classification."""

import time
from typing import Optional
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import numpy as np

from src.config import get_settings
from src.schemas import ActionClassification, ActionContext, ClassificationResult


class DeBERTaClassifier:
    """Fine-tuned DeBERTa model for classifying agent actions."""

    # Class mapping
    LABEL_MAP = {
        0: ActionClassification.GREEN,
        1: ActionClassification.YELLOW,
        2: ActionClassification.RED,
    }

    REVERSE_LABEL_MAP = {v: k for k, v in LABEL_MAP.items()}

    def __init__(self, model_path: Optional[str] = None, device: Optional[str] = None):
        """Initialize classifier.

        Args:
            model_path: Path to fine-tuned model. Uses default if None.
            device: Device to run on ("cpu" or "cuda"). Uses config if None.
        """
        settings = get_settings()
        self.model_path = model_path or settings.classifier_model_path
        self.device = device or settings.classifier_device
        self.batch_size = settings.classifier_batch_size

        # Load model and tokenizer
        self.model = None
        self.tokenizer = None
        self.loaded = False

        self._load_model()

    def _load_model(self) -> None:
        """Load model and tokenizer from disk."""
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_path,
                num_labels=3,  # Green, Yellow, Red
            )
            self.model.to(self.device)
            self.model.eval()
            self.loaded = True
            print(f"✓ Loaded DeBERTa classifier from {self.model_path}")
        except Exception as e:
            print(f"✗ Failed to load classifier: {e}")
            self.loaded = False
            # Fall back to baseline rule-based classifier
            self.model = None
            self.tokenizer = None

    def _action_to_text(self, context: ActionContext) -> str:
        """Convert action context to text for classification."""
        parts = [
            f"Action: {context.action_type.value}",
            f"Command: {context.command[:200]}",
            f"Target: {context.target_resource}",
            f"Agent: {context.agent_id}",
            f"Scope: {context.agent_scope}",
        ]

        if context.is_prod:
            parts.append("Production: yes")
        if context.touches_credentials:
            parts.append("Credentials: yes")
        if context.touches_config:
            parts.append("Config files: yes")

        if context.recent_actions:
            parts.append(f"Recent actions: {', '.join(context.recent_actions)}")

        return " | ".join(parts)

    def classify(self, context: ActionContext) -> ClassificationResult:
        """Classify an action as green/yellow/red.

        Args:
            context: Action context for classification.

        Returns:
            Classification result with confidence score.
        """
        start_time = time.time()

        # Use ML classifier if available, otherwise use baseline
        if self.loaded and self.model is not None:
            result = self._classify_ml(context)
        else:
            result = self._classify_baseline(context)

        elapsed_ms = (time.time() - start_time) * 1000
        result.model_version = "1.0"

        return result

    def _classify_ml(self, context: ActionContext) -> ClassificationResult:
        """Classify using fine-tuned DeBERTa model."""
        try:
            # Convert to text
            text = self._action_to_text(context)

            # Tokenize
            inputs = self.tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Forward pass
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probs = torch.softmax(logits, dim=-1)

            # Get prediction
            pred_label = torch.argmax(probs, dim=-1).item()
            confidence = float(probs[0, pred_label].item())

            classification = self.LABEL_MAP[pred_label]

            return ClassificationResult(
                classification=classification,
                confidence=confidence,
                reasoning=f"ML classification: {pred_label}",
                model_version="1.0",
            )

        except Exception as e:
            print(f"ML classification failed: {e}. Falling back to baseline.")
            return self._classify_baseline(context)

    def _classify_baseline(self, context: ActionContext) -> ClassificationResult:
        """Baseline rule-based classifier for fallback."""
        classification = ActionClassification.YELLOW
        confidence = 0.5
        reasoning = []

        # Rule 1: Read-only operations are usually green
        if context.action_type.value.endswith("_read") or context.action_type == "db_select":
            classification = ActionClassification.GREEN
            confidence = 0.95
            reasoning.append("Read-only operation")

        # Rule 2: Directory listing is safe
        if context.action_type.value == "dir_list":
            classification = ActionClassification.GREEN
            confidence = 0.95
            reasoning.append("Directory listing (safe)")

        # Rule 3: Destructive operations in production = RED
        if context.is_prod and context.action_type.value.endswith("_delete"):
            classification = ActionClassification.RED
            confidence = 0.99
            reasoning.append("Destructive operation on production")

        # Rule 4: Accessing credentials = RED
        if context.touches_credentials:
            classification = ActionClassification.RED
            confidence = 0.98
            reasoning.append("Touches credential files")

        # Rule 5: Config file modifications = YELLOW/RED depending on scope
        if context.touches_config:
            if context.is_prod:
                classification = ActionClassification.RED
                confidence = 0.95
                reasoning.append("Modifying production config")
            else:
                classification = ActionClassification.YELLOW
                confidence = 0.80
                reasoning.append("Modifying config files")

        # Rule 6: Database deletes without where clause = RED
        if context.action_type == "db_delete" and "where" not in context.command.lower():
            classification = ActionClassification.RED
            confidence = 0.95
            reasoning.append("DELETE without WHERE clause")

        # Rule 7: Write operations generally yellow
        if context.action_type.value.endswith("_write") or context.action_type.value.endswith("_insert"):
            if classification == ActionClassification.YELLOW:  # Not already red
                classification = ActionClassification.YELLOW
                confidence = 0.75
                reasoning.append("Write operation")

        # Rule 8: Bash with rm, dd, mkfs = RED
        if context.action_type == "bash_run":
            dangerous_patterns = ["rm -rf", "dd if=", "mkfs", ":(){ :|:& };:"]
            if any(pattern in context.command for pattern in dangerous_patterns):
                classification = ActionClassification.RED
                confidence = 0.99
                reasoning.append("Dangerous bash pattern detected")

        return ClassificationResult(
            classification=classification,
            confidence=confidence,
            reasoning=" | ".join(reasoning) if reasoning else "Baseline rules applied",
            model_version="baseline",
        )

    def batch_classify(
        self, contexts: list[ActionContext]
    ) -> list[ClassificationResult]:
        """Classify multiple actions at once.

        Args:
            contexts: List of action contexts.

        Returns:
            List of classification results.
        """
        return [self.classify(ctx) for ctx in contexts]

    def health_check(self) -> bool:
        """Check if classifier is loaded and working."""
        if not self.loaded:
            return False

        # Try a dummy classification
        try:
            dummy = ActionContext(
                action_type="file_read",
                command="ls /tmp",
                target_resource="/tmp",
                agent_id="test",
                agent_scope="test",
            )
            result = self.classify(dummy)
            return result.classification in [
                ActionClassification.GREEN,
                ActionClassification.YELLOW,
                ActionClassification.RED,
            ]
        except Exception:
            return False


# Global classifier instance
_classifier: Optional[DeBERTaClassifier] = None


def get_classifier() -> DeBERTaClassifier:
    """Get global classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = DeBERTaClassifier()
    return _classifier


def load_classifier(force_reload: bool = False) -> DeBERTaClassifier:
    """Load or reload the classifier.

    Args:
        force_reload: Force reload even if already loaded.

    Returns:
        DeBERTaClassifier instance.
    """
    global _classifier
    if force_reload or _classifier is None:
        _classifier = DeBERTaClassifier()
    return _classifier
