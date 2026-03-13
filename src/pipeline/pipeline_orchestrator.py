import logging
from src.pipeline.health_monitor import get_pipeline_health
from src.pipeline.bball_ref_fallback import fetch_bball_ref_standings

def run_pipeline_cycle(data_dir: str) -> dict:
    """Coordinate the pipeline health check and fallback ingest."""
    health = get_pipeline_health(data_dir)
    
    if not health["is_stale"]:
        logging.info("Pipeline data is fresh. No fallback needed.")
        return {
            "health": health,
            "action": "skipped",
            "data": None
        }
    
    logging.warning(f"Data is stale ({health['data_age_hours']}h). Triggering fallback ingest.")
    fallback_data = fetch_bball_ref_standings()
    
    if fallback_data:
        logging.info("Fallback standings successfully retrieved from Basketball Reference.")
        return {
            "health": health,
            "action": "fallback_success",
            "data": fallback_data
        }
    else:
        logging.error("Fallback standings retrieval failed.")
        return {
            "health": health,
            "action": "fallback_failure",
            "data": None
        }
