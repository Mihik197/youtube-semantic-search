# ingest_data.py
import sys
from src.core.pipeline import DataIngestionPipeline
from src.config import IS_CONFIG_VALID

def run_ingestion():
    """Handles the full data ingestion pipeline."""
    print("--- Running Data Ingestion Pipeline ---")

    if not IS_CONFIG_VALID:
        print("Configuration is invalid. Please check settings and file paths.")
        return False

    try:
        pipeline = DataIngestionPipeline()
        success = pipeline.run()
        return success
    except Exception as e:
        print(f"An error occurred during the ingestion process: {e}")
        return False

if __name__ == "__main__":
    if run_ingestion():
        print("\n--- Ingestion completed successfully. ---")
        sys.exit(0)  # Exit with success code
    else:
        print("\n--- Ingestion process failed or encountered errors. ---")
        sys.exit(1)  # Exit with failure code
