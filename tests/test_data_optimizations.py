import asyncio
import time
from datetime import date, timedelta
import os
import pandas as pd

from data_manager.data_reader import DataReader
from logger import get_logger

logger = get_logger(__name__)

async def test_parquet_storage():
    """Test that parquet storage works correctly."""
    reader = DataReader()
    
    # Choose a symbol that's likely to exist in the data
    symbol = "AAPL"
    
    # Define date range
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    try:
        # Get data (this will create parquet file if it doesn't exist)
        data = await reader.get_data(symbol, start_date, end_date)
        logger.info(f"Successfully loaded data for {symbol}")
        
        # Check if parquet file was created
        parquet_path = os.path.join(reader.DATA_PARQUET_LOCATION, f"{symbol}.parquet")
        assert os.path.exists(parquet_path), f"Parquet file {parquet_path} was not created"
        logger.info(f"Parquet file exists at {parquet_path}")
        
        # Verify we can read the parquet file directly
        df = pd.read_parquet(parquet_path)
        assert not df.empty, "Parquet file is empty"
        logger.info(f"Parquet file contains {len(df)} rows")
        
        return True
    except Exception as e:
        logger.error(f"Error testing parquet storage: {str(e)}")
        return False

async def test_caching():
    """Test that caching works correctly."""
    reader = DataReader()
    
    # Choose a symbol that's likely to exist in the data
    symbol = "MSFT"
    
    # Define date range
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    try:
        # First access (cache miss)
        start_time = time.time()
        data1 = await reader.get_data(symbol, start_date, end_date)
        first_access_time = time.time() - start_time
        logger.info(f"First access took {first_access_time:.4f} seconds")
        
        # Second access (should be cache hit)
        start_time = time.time()
        data2 = await reader.get_data(symbol, start_date, end_date)
        second_access_time = time.time() - start_time
        logger.info(f"Second access took {second_access_time:.4f} seconds")
        
        # Verify cache is working (second access should be faster)
        assert second_access_time < first_access_time, "Caching doesn't seem to be working (second access not faster)"
        logger.info(f"Caching is working: second access was {first_access_time/second_access_time:.1f}x faster")
        
        # Verify data is the same
        assert data1.equals(data2), "Data from cache doesn't match original data"
        
        return True
    except Exception as e:
        logger.error(f"Error testing caching: {str(e)}")
        return False

async def main():
    """Run all tests."""
    logger.info("Testing data optimizations...")
    
    # Test parquet storage
    logger.info("Testing parquet storage...")
    parquet_result = await test_parquet_storage()
    
    # Test caching
    logger.info("Testing caching...")
    cache_result = await test_caching()
    
    # Print summary
    logger.info("\nTest Results:")
    logger.info(f"Parquet Storage: {'PASSED' if parquet_result else 'FAILED'}")
    logger.info(f"Caching: {'PASSED' if cache_result else 'FAILED'}")
    
    if parquet_result and cache_result:
        logger.info("\nAll tests PASSED!")
    else:
        logger.info("\nSome tests FAILED!")

if __name__ == "__main__":
    asyncio.run(main())