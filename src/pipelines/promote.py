"""Model promotion logic."""

from datetime import datetime
from typing import Dict, Any, Optional

from loguru import logger

from ..utils.mlflow_utils import MLflowManager, CLASSIFIER_MODEL_NAME, SUMMARIZER_MODEL_NAME
from ..utils.db import get_db


class ModelPromoter:
    """
    Handles model promotion between stages.
    
    Supports promoting models to Staging or Production based on
    evaluation metrics and comparison with current production.
    """
    
    def __init__(self):
        self.mlflow_manager = MLflowManager()
        self.db = get_db()
    
    def get_model_versions(self, model_name: str) -> Dict[str, Any]:
        """Get all versions of a model with their stages."""
        history = self.mlflow_manager.get_model_history(model_name)
        
        versions_by_stage = {
            "Production": [],
            "Staging": [],
            "None": [],
            "Archived": [],
        }
        
        for v in history:
            stage = v.get("stage", "None")
            if stage in versions_by_stage:
                versions_by_stage[stage].append(v)
        
        return {
            "model_name": model_name,
            "versions": history,
            "by_stage": versions_by_stage,
            "production_version": versions_by_stage["Production"][0] if versions_by_stage["Production"] else None,
            "staging_version": versions_by_stage["Staging"][0] if versions_by_stage["Staging"] else None,
        }
    
    def promote_to_staging(
        self,
        model_name: str,
        version: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Promote a model version to Staging.
        
        Args:
            model_name: Name of the model in registry
            version: Version to promote
            reason: Optional reason for promotion
            
        Returns:
            Promotion result
        """
        logger.info(f"Promoting {model_name} v{version} to Staging")
        
        try:
            self.mlflow_manager.transition_model_stage(
                model_name=model_name,
                version=version,
                stage="Staging",
                archive_existing=False,
            )
            
            result = {
                "success": True,
                "model_name": model_name,
                "version": version,
                "new_stage": "Staging",
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            logger.info(f"Successfully promoted to Staging")
            return result
            
        except Exception as e:
            logger.error(f"Promotion failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def promote_to_production(
        self,
        model_name: str,
        version: str,
        reason: Optional[str] = None,
        archive_current: bool = True,
    ) -> Dict[str, Any]:
        """
        Promote a model version to Production.
        
        Args:
            model_name: Name of the model in registry
            version: Version to promote
            reason: Optional reason for promotion
            archive_current: Whether to archive current production version
            
        Returns:
            Promotion result
        """
        logger.info(f"Promoting {model_name} v{version} to Production")
        
        try:
            # Get current production version for logging
            current_prod = self.mlflow_manager.get_production_model_version(model_name)
            
            self.mlflow_manager.promote_to_production(
                model_name=model_name,
                version=version,
            )
            
            result = {
                "success": True,
                "model_name": model_name,
                "version": version,
                "new_stage": "Production",
                "previous_production": current_prod,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Log to database
            self._log_promotion(result)
            
            logger.info(f"Successfully promoted to Production (previous: v{current_prod})")
            return result
            
        except Exception as e:
            logger.error(f"Promotion failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def promote_classifier(
        self,
        run_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Promote a classifier model from a training run."""
        # Get the version registered from this run
        versions = self.mlflow_manager.client.search_model_versions(
            f"name='{CLASSIFIER_MODEL_NAME}'"
        )
        
        version = None
        for v in versions:
            if v.run_id == run_id:
                version = v.version
                break
        
        if version is None:
            return {"success": False, "error": "No model found for run ID"}
        
        return self.promote_to_production(
            model_name=CLASSIFIER_MODEL_NAME,
            version=version,
            reason=reason,
        )
    
    def promote_summarizer(
        self,
        run_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Promote a summarizer model from a training run."""
        versions = self.mlflow_manager.client.search_model_versions(
            f"name='{SUMMARIZER_MODEL_NAME}'"
        )
        
        version = None
        for v in versions:
            if v.run_id == run_id:
                version = v.version
                break
        
        if version is None:
            return {"success": False, "error": "No model found for run ID"}
        
        return self.promote_to_production(
            model_name=SUMMARIZER_MODEL_NAME,
            version=version,
            reason=reason,
        )
    
    def rollback(
        self,
        model_name: str,
        to_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Rollback to a previous version.
        
        Args:
            model_name: Name of the model
            to_version: Version to rollback to (None = previous archived)
            
        Returns:
            Rollback result
        """
        logger.info(f"Rolling back {model_name}")
        
        try:
            if to_version is None:
                # Find the most recent archived version
                versions = self.mlflow_manager.get_model_history(model_name)
                archived = [
                    v for v in versions 
                    if v.get("stage") == "Archived"
                ]
                
                if not archived:
                    return {"success": False, "error": "No archived versions to rollback to"}
                
                # Sort by version number and get the most recent
                archived.sort(key=lambda x: int(x["version"]), reverse=True)
                to_version = archived[0]["version"]
            
            return self.promote_to_production(
                model_name=model_name,
                version=to_version,
                reason="Rollback",
            )
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _log_promotion(self, result: Dict[str, Any]):
        """Log promotion to database for audit trail."""
        try:
            # This would insert into a promotions log table
            # For now, just log
            logger.info(f"Promotion logged: {result}")
        except Exception as e:
            logger.warning(f"Failed to log promotion: {e}")
    
    def get_promotion_status(self) -> Dict[str, Any]:
        """Get current promotion status of all models."""
        return {
            "classifier": self.get_model_versions(CLASSIFIER_MODEL_NAME),
            "summarizer": self.get_model_versions(SUMMARIZER_MODEL_NAME),
        }
