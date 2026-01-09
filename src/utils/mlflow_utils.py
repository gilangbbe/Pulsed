"""MLflow utilities for model tracking and registry."""

import os
from typing import Optional, Dict, Any, List
from pathlib import Path

import mlflow
from mlflow.tracking import MlflowClient
from mlflow.entities.model_registry import ModelVersion
from loguru import logger

from .config import config


class MLflowManager:
    """Manager for MLflow experiment tracking and model registry."""
    
    def __init__(self):
        self.tracking_uri = config.mlflow.tracking_uri
        self.experiment_name = config.mlflow.experiment_name
        mlflow.set_tracking_uri(self.tracking_uri)
        self.client = MlflowClient()
        self._setup_experiment()
    
    def _setup_experiment(self):
        """Setup or get the MLflow experiment."""
        experiment = mlflow.get_experiment_by_name(self.experiment_name)
        if experiment is None:
            self.experiment_id = mlflow.create_experiment(self.experiment_name)
            logger.info(f"Created new experiment: {self.experiment_name}")
        else:
            self.experiment_id = experiment.experiment_id
        mlflow.set_experiment(self.experiment_name)
    
    def start_run(self, run_name: str, tags: Optional[Dict[str, str]] = None) -> mlflow.ActiveRun:
        """Start a new MLflow run."""
        return mlflow.start_run(run_name=run_name, tags=tags)
    
    def log_params(self, params: Dict[str, Any]):
        """Log parameters to the current run."""
        mlflow.log_params(params)
    
    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None):
        """Log metrics to the current run."""
        mlflow.log_metrics(metrics, step=step)
    
    def log_model(
        self,
        model,
        artifact_path: str,
        registered_model_name: Optional[str] = None,
        **kwargs
    ):
        """Log a model to MLflow."""
        if "transformers" in str(type(model)):
            mlflow.transformers.log_model(
                model,
                artifact_path=artifact_path,
                registered_model_name=registered_model_name,
                **kwargs
            )
        else:
            mlflow.sklearn.log_model(
                model,
                artifact_path=artifact_path,
                registered_model_name=registered_model_name,
                **kwargs
            )
    
    def log_pytorch_model(
        self,
        pytorch_model,
        artifact_path: str,
        registered_model_name: Optional[str] = None,
    ):
        """Log a PyTorch model."""
        mlflow.pytorch.log_model(
            pytorch_model,
            artifact_path=artifact_path,
            registered_model_name=registered_model_name,
        )
    
    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None):
        """Log an artifact to MLflow."""
        mlflow.log_artifact(local_path, artifact_path)
    
    def register_model(self, model_uri: str, name: str) -> ModelVersion:
        """Register a model to the model registry."""
        return mlflow.register_model(model_uri, name)
    
    def get_latest_version(
        self, 
        model_name: str, 
        stages: Optional[List[str]] = None
    ) -> Optional[ModelVersion]:
        """Get the latest version of a registered model."""
        try:
            if stages is None:
                stages = ["Production", "Staging", "None"]
            
            versions = self.client.get_latest_versions(model_name, stages=stages)
            if versions:
                return versions[0]
            return None
        except Exception as e:
            logger.warning(f"Could not get latest version for {model_name}: {e}")
            return None
    
    def get_production_model_version(self, model_name: str) -> Optional[str]:
        """Get the production model version string."""
        version = self.get_latest_version(model_name, stages=["Production"])
        if version:
            return version.version
        return None
    
    def transition_model_stage(
        self,
        model_name: str,
        version: str,
        stage: str,
        archive_existing: bool = True,
    ):
        """Transition a model version to a new stage."""
        self.client.transition_model_version_stage(
            name=model_name,
            version=version,
            stage=stage,
            archive_existing_versions=archive_existing,
        )
        logger.info(f"Transitioned {model_name} v{version} to {stage}")
    
    def promote_to_production(self, model_name: str, version: str):
        """Promote a model version to production."""
        self.transition_model_stage(
            model_name=model_name,
            version=version,
            stage="Production",
            archive_existing=True,
        )
    
    def load_model(self, model_name: str, stage: str = "Production"):
        """Load a model from the registry."""
        model_uri = f"models:/{model_name}/{stage}"
        try:
            return mlflow.pyfunc.load_model(model_uri)
        except Exception as e:
            logger.error(f"Failed to load model {model_name} from {stage}: {e}")
            raise
    
    def load_pytorch_model(self, model_name: str, stage: str = "Production"):
        """Load a PyTorch model from the registry."""
        model_uri = f"models:/{model_name}/{stage}"
        return mlflow.pytorch.load_model(model_uri)
    
    def load_transformers_model(self, model_name: str, stage: str = "Production"):
        """Load a transformers model from the registry."""
        model_uri = f"models:/{model_name}/{stage}"
        return mlflow.transformers.load_model(model_uri)
    
    def get_model_history(self, model_name: str) -> List[Dict[str, Any]]:
        """Get version history of a registered model."""
        try:
            versions = self.client.search_model_versions(f"name='{model_name}'")
            return [
                {
                    "version": v.version,
                    "stage": v.current_stage,
                    "status": v.status,
                    "creation_timestamp": v.creation_timestamp,
                    "description": v.description,
                    "run_id": v.run_id,
                }
                for v in versions
            ]
        except Exception as e:
            logger.warning(f"Could not get model history for {model_name}: {e}")
            return []
    
    def get_run_metrics(self, run_id: str) -> Dict[str, float]:
        """Get metrics from a specific run."""
        run = self.client.get_run(run_id)
        return run.data.metrics
    
    def compare_models(
        self,
        model_name: str,
        version_a: str,
        version_b: str,
        metric_name: str,
    ) -> Dict[str, Any]:
        """Compare two model versions on a specific metric."""
        versions = self.client.search_model_versions(f"name='{model_name}'")
        
        metrics = {}
        for v in versions:
            if v.version in [version_a, version_b]:
                run = self.client.get_run(v.run_id)
                metrics[v.version] = run.data.metrics.get(metric_name, 0)
        
        improvement = metrics.get(version_b, 0) - metrics.get(version_a, 0)
        
        return {
            "version_a": version_a,
            "version_b": version_b,
            "metric_name": metric_name,
            "value_a": metrics.get(version_a, 0),
            "value_b": metrics.get(version_b, 0),
            "improvement": improvement,
            "improved": improvement > 0,
        }
    
    def cleanup_old_versions(self, model_name: str, keep_last: int = 5):
        """Archive old model versions, keeping only the most recent ones."""
        versions = self.client.search_model_versions(f"name='{model_name}'")
        
        # Sort by version number (descending)
        sorted_versions = sorted(
            versions, 
            key=lambda x: int(x.version), 
            reverse=True
        )
        
        # Keep production and most recent versions
        for i, v in enumerate(sorted_versions):
            if v.current_stage == "Production":
                continue
            if i >= keep_last and v.current_stage != "Archived":
                self.transition_model_stage(
                    model_name=model_name,
                    version=v.version,
                    stage="Archived",
                    archive_existing=False,
                )


# Model names for the registry
CLASSIFIER_MODEL_NAME = "pulsed-classifier"
SUMMARIZER_MODEL_NAME = "pulsed-summarizer"
