"""Summarizer training module."""

from typing import Dict, Any, Optional, List
from pathlib import Path

import torch
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    DataCollatorForSeq2Seq,
)
from sklearn.model_selection import train_test_split
import mlflow
from loguru import logger

from .config import SummarizerConfig
from .evaluate import SummarizerEvaluator
from ...utils.mlflow_utils import MLflowManager, SUMMARIZER_MODEL_NAME
from ...utils.summary_utils import RougeEvaluator


class SummaryDataset(Dataset):
    """Dataset for summary fine-tuning."""
    
    def __init__(
        self,
        sources: List[str],
        targets: List[str],
        tokenizer,
        max_source_length: int = 1024,
        max_target_length: int = 256,
    ):
        self.sources = sources
        self.targets = targets
        self.tokenizer = tokenizer
        self.max_source_length = max_source_length
        self.max_target_length = max_target_length
    
    def __len__(self):
        return len(self.sources)
    
    def __getitem__(self, idx):
        source = self.sources[idx]
        target = self.targets[idx]
        
        source_encoding = self.tokenizer(
            source,
            truncation=True,
            max_length=self.max_source_length,
            padding="max_length",
            return_tensors="pt",
        )
        
        target_encoding = self.tokenizer(
            target,
            truncation=True,
            max_length=self.max_target_length,
            padding="max_length",
            return_tensors="pt",
        )
        
        labels = target_encoding["input_ids"].squeeze()
        # Replace padding token id with -100 so it's ignored in loss
        labels[labels == self.tokenizer.pad_token_id] = -100
        
        return {
            "input_ids": source_encoding["input_ids"].squeeze(),
            "attention_mask": source_encoding["attention_mask"].squeeze(),
            "labels": labels,
        }


class SummarizerTrainer:
    """Trainer for the article summarizer."""
    
    def __init__(self, config: Optional[SummarizerConfig] = None):
        self.config = config or SummarizerConfig()
        self.tokenizer = None
        self.model = None
        self.mlflow_manager = MLflowManager()
        self.rouge_evaluator = RougeEvaluator()
    
    def _prepare_data(
        self,
        articles: List[Dict[str, Any]],
        test_size: float = 0.2,
    ) -> tuple:
        """
        Prepare training and validation datasets.
        
        Args:
            articles: List of articles with source text and summary
            test_size: Proportion for validation set
            
        Returns:
            Tuple of (train_dataset, val_dataset)
        """
        sources = []
        targets = []
        
        for article in articles:
            # Get source text
            title = article.get("title", "")
            abstract = article.get("abstract", "") or ""
            full_text = article.get("full_text", "") or ""
            
            if full_text:
                source = f"{title}\n\n{full_text}"
            else:
                source = f"{title}\n\n{abstract}"
            
            # Get target summary (from edited feedback or reference)
            target = (
                article.get("summary_edited_text") or 
                article.get("reference_summary") or
                article.get("summary_text")
            )
            
            if source and target:
                sources.append(source)
                targets.append(target)
        
        if not sources:
            raise ValueError("No valid source-target pairs found")
        
        logger.info(f"Prepared {len(sources)} source-target pairs for training")
        
        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            sources, targets, test_size=test_size, random_state=self.config.seed
        )
        
        logger.info(f"Train: {len(X_train)}, Val: {len(X_val)}")
        
        # Create datasets
        train_dataset = SummaryDataset(
            X_train, y_train, self.tokenizer,
            self.config.max_input_length,
            self.config.detailed_max_length,
        )
        val_dataset = SummaryDataset(
            X_val, y_val, self.tokenizer,
            self.config.max_input_length,
            self.config.detailed_max_length,
        )
        
        return train_dataset, val_dataset
    
    def train(
        self,
        articles: List[Dict[str, Any]],
        output_dir: Optional[str] = None,
        register_model: bool = True,
    ) -> Dict[str, Any]:
        """
        Fine-tune the summarizer model.
        
        Args:
            articles: List of articles with source text and reference summaries
            output_dir: Directory to save the model
            register_model: Whether to register model with MLflow
            
        Returns:
            Dictionary with training results and metrics
        """
        output_dir = output_dir or self.config.output_dir
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize tokenizer and model
        logger.info(f"Loading model: {self.config.model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.config.model_name)
        
        # Prepare data
        train_dataset, val_dataset = self._prepare_data(articles)
        
        # Data collator
        data_collator = DataCollatorForSeq2Seq(
            self.tokenizer,
            model=self.model,
            padding=True,
        )
        
        # Start MLflow run
        with self.mlflow_manager.start_run(run_name="summarizer_training") as run:
            run_id = run.info.run_id
            
            # Log parameters
            self.mlflow_manager.log_params(self.config.to_dict())
            self.mlflow_manager.log_params({
                "train_samples": len(train_dataset),
                "val_samples": len(val_dataset),
            })
            
            # Training arguments
            training_args = Seq2SeqTrainingArguments(
                output_dir=output_dir,
                num_train_epochs=self.config.num_epochs,
                per_device_train_batch_size=self.config.batch_size,
                per_device_eval_batch_size=self.config.batch_size,
                learning_rate=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
                warmup_ratio=self.config.warmup_ratio,
                gradient_accumulation_steps=self.config.gradient_accumulation_steps,
                evaluation_strategy="epoch",
                save_strategy="epoch",
                load_best_model_at_end=True,
                predict_with_generate=True,
                generation_max_length=self.config.detailed_max_length,
                fp16=self.config.fp16 and torch.cuda.is_available(),
                logging_steps=50,
                save_total_limit=2,
                seed=self.config.seed,
                report_to="none",
            )
            
            # Create trainer
            trainer = Seq2SeqTrainer(
                model=self.model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=val_dataset,
                data_collator=data_collator,
                tokenizer=self.tokenizer,
            )
            
            # Train
            logger.info("Starting training...")
            train_result = trainer.train()
            
            # Log training metrics
            self.mlflow_manager.log_metrics({
                "train_loss": train_result.training_loss,
                "train_runtime": train_result.metrics.get("train_runtime", 0),
            })
            
            # Evaluate
            logger.info("Evaluating model...")
            eval_results = trainer.evaluate()
            
            self.mlflow_manager.log_metrics({
                f"eval_{k.replace('eval_', '')}": v 
                for k, v in eval_results.items()
            })
            
            # Save model
            trainer.save_model(output_dir)
            self.tokenizer.save_pretrained(output_dir)
            
            # Log model to MLflow
            if register_model:
                logger.info("Registering model with MLflow...")
                mlflow.transformers.log_model(
                    transformers_model={
                        "model": trainer.model,
                        "tokenizer": self.tokenizer,
                    },
                    artifact_path="model",
                    registered_model_name=SUMMARIZER_MODEL_NAME,
                )
            
            results = {
                "run_id": run_id,
                "train_loss": train_result.training_loss,
                "eval_metrics": eval_results,
                "model_path": output_dir,
            }
            
            logger.info("Training complete")
            
            return results
    
    def train_from_feedback(
        self,
        feedback_articles: List[Dict[str, Any]],
        existing_model_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fine-tune model on feedback data with edited summaries.
        
        Args:
            feedback_articles: Articles with summary feedback and edits
            existing_model_path: Path to existing model to fine-tune
            
        Returns:
            Training results
        """
        # Filter to only include articles with edited summaries
        edited = [
            a for a in feedback_articles 
            if a.get("summary_edited_text") or a.get("summary_rating") == "good"
        ]
        
        if len(edited) < 10:
            logger.warning(f"Only {len(edited)} feedback samples, may not be enough for training")
        
        if existing_model_path:
            self.config.model_name = existing_model_path
        
        # Reduce epochs for fine-tuning
        self.config.num_epochs = 2
        self.config.learning_rate = 1e-5
        
        return self.train(
            articles=edited,
            output_dir=f"{self.config.output_dir}_finetuned",
            register_model=True,
        )
