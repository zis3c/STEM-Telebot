import os
from datetime import datetime, timedelta
import sys

# Add the project directory to sys.path to import project modules
sys.path.append(r'C:\Users\RADZ\project io\STEM Telebot')

from database import db

def verify():
    print("--- Maintenance Logic Verification ---")
    
    # 1. Simulate a past maintenance date
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    with open("last_maint.txt", "w") as f:
        f.write(yesterday)
    print(f"Set last_maint.txt to: {yesterday}")
    
    # 2. Check if Database reports it correctly
    last_run = db.get_last_maintenance()
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"Database reports last run: {last_run}")
    print(f"Current date: {current_date}")
    
    if last_run != current_date:
        print("✅ SUCCESS: Maintenance is recognized as DUE.")
    else:
        print("❌ FAILURE: Maintenance should be due but isn't.")
        
    # 3. Simulate maintenance update
    db.update_last_maintenance()
    new_last_run = db.get_last_maintenance()
    print(f"After update, last run is: {new_last_run}")
    
    if new_last_run == current_date:
        print("✅ SUCCESS: Last run date updated correctly.")
    else:
        print("❌ FAILURE: Last run date did not update.")

if __name__ == "__main__":
    verify()
