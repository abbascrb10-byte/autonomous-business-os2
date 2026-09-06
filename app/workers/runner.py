import asyncio
import sys
from app.workers.manager import worker_manager
import structlog

logger = structlog.get_logger()

async def main():
    logger.info("Starting GPIE Background Worker Consumer...")
    # Run consumer loops for registered queues
    await asyncio.gather(
        worker_manager.run_worker_loop("demand_ingestion"),
        worker_manager.run_worker_loop("intent_processing"),
        worker_manager.run_worker_loop("offer_discovery"),
        worker_manager.run_worker_loop("conversion_processing")
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
