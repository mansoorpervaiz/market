import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from data_manager.symbol_manager import SymbolManager

def test_load_russell_1000_symbols():
    """Test loading Russell 1000 symbols from Wikipedia."""
    sm = SymbolManager()
    symbols = sm.load_russell_1000_symbols()
    
    # Print the number of symbols loaded
    print(f"Loaded {len(symbols)} symbols from Russell 1000 Index")
    
    # Print the first 10 symbols
    print("First 10 symbols:")
    for i, symbol in enumerate(symbols[:10]):
        print(f"{i+1}. {symbol}")
    
    # Verify that we have a reasonable number of symbols
    # The Russell 1000 should have around 1000 symbols, but the exact number may vary
    assert len(symbols) > 500, f"Expected at least 500 symbols, but got {len(symbols)}"
    
    print("Test passed!")
    return symbols

if __name__ == "__main__":
    symbols = test_load_russell_1000_symbols()
    
    # Save symbols to a file
    with open("russell_1000_symbols.txt", "w") as f:
        for symbol in symbols:
            f.write(symbol + "\n")
    
    print(f"Saved {len(symbols)} symbols to russell_1000_symbols.txt")