import sys
import os
from datetime import date

# Ensure garmindb is in the path
sys.path.append(os.getcwd())

from garmindb.data.repositories.sqlite import SQLiteHealthRepository
from garmindb.garmin_connect_config_manager import GarminConnectConfigManager
from garmindb.garmindb import GarminDb, DailySummary

def main():
    config = GarminConnectConfigManager()
    db_params = config.get_db_params()
    
    print(f"Connecting to DB: {db_params}")
    garmin_db = GarminDb(db_params)
    
    print("Testing manual insertion into DailySummary...")
    
    test_data = {
        'day': date(2025, 12, 25),
        'steps': 5000,
        'bb_charged': 50,
        'description': 'Manual Insert Test'
    }
    
    try:
        DailySummary.insert_or_update(garmin_db, test_data)
        print("Insert command executed successfully.")
    except Exception as e:
        print(f"Insert failed with error: {e}")

if __name__ == "__main__":
    main()