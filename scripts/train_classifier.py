"""Fine-tune DeBERTa classifier on synthetic agent action dataset."""

import json
from pathlib import Path
from typing import Optional

import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding,
)
from datasets import Dataset

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_training_data(data_path: str = "data/training_data.jsonl") -> tuple[list[str], list[int]]:
    """Load training data from JSONL file.

    Args:
        data_path: Path to training data file.

    Returns:
        Tuple of (texts, labels).
    """
    texts = []
    labels = []
    label_map = {"green": 0, "yellow": 1, "red": 2}

    with open(data_path, "r") as f:
        for line in f:
            record = json.loads(line)
            texts.append(record["text"])
            labels.append(label_map[record["label"]])

    return texts, labels


def train_classifier(
    data_path: str = "data/training_data.jsonl",
    output_path: str = "models/deberta-classifier",
    model_name: str = "microsoft/deberta-v3-base",
    device: Optional[str] = None,
    epochs: int = 3,
    batch_size: int = 32,
):
    """Fine-tune DeBERTa classifier.

    Args:
        data_path: Path to training data JSONL file.
        output_path: Path to save fine-tuned model.
        model_name: Hugging Face model name.
        device: Device to train on ('cpu' or 'cuda').
        epochs: Number of training epochs.
        batch_size: Training batch size.
    """
    print("🤖 Fine-tuning DeBERTa classifier...\n")

    # Determine device
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    # Load training data
    print(f"Loading training data from {data_path}...")
    if not Path(data_path).exists():
        print(f"✗ Training data not found. Run generate_training_data.py first.")
        return

    texts, labels = load_training_data(data_path)
    print(f"✓ Loaded {len(texts)} examples")
    print(f"  - Green: {labels.count(0)}")
    print(f"  - Yellow: {labels.count(1)}")
    print(f"  - Red: {labels.count(2)}\n")

    # Load model and tokenizer
    print(f"Loading base model: {model_name}...")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=3,
        problem_type="single_label_classification",
    )
    model.to(device)
    print("✓ Model loaded\n")

    # Tokenize
    print("Tokenizing texts...")

    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            padding="max_length",
            truncation=True,
            max_length=512,
        )

    dataset = Dataset.from_dict({"text": texts, "label": labels})
    tokenized_datasets = dataset.map(tokenize_function, batched=True)

    # Split into train/val
    split = tokenized_datasets.train_test_split(test_size=0.1, seed=42)
    train_dataset = split["train"]
    eval_dataset = split["test"]

    print(f"✓ Tokenized {len(train_dataset)} training examples")
    print(f"✓ Tokenized {len(eval_dataset)} validation examples\n")

    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_path,
        learning_rate=2e-5,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        num_train_epochs=epochs,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        push_to_hub=False,
        logging_steps=10,
    )

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=DataCollatorWithPadding(tokenizer),
    )

    # Train
    print("🔄 Starting training...")
    trainer.train()

    # Save
    print(f"\nSaving fine-tuned model to {output_path}...")
    model.save_pretrained(output_path)
    tokenizer.save_pretrained(output_path)
    print("✓ Model saved\n")

    # Evaluate
    print("Evaluating on test set...")
    results = trainer.evaluate()
    print(f"✓ Test results:")
    print(f"  Accuracy: {results.get('eval_accuracy', 0):.2%}")
    print(f"  Loss: {results.get('eval_loss', 0):.4f}\n")

    print("✓ Training complete!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data",
        default="data/training_data.jsonl",
        help="Path to training data JSONL file",
    )
    parser.add_argument(
        "--output",
        default="models/deberta-classifier",
        help="Path to save fine-tuned model",
    )
    parser.add_argument(
        "--model",
        default="microsoft/deberta-v3-base",
        help="Base model name from Hugging Face",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="Number of training epochs",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Training batch size",
    )

    args = parser.parse_args()

    train_classifier(
        data_path=args.data,
        output_path=args.output,
        model_name=args.model,
        epochs=args.epochs,
        batch_size=args.batch_size,
    )
