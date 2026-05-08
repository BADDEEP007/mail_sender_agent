#!/bin/bash

# Stop script if any command fails
set -e

echo "Activating virtual environment..."

# Activate virtual environment
source ../venv/bin/activate

echo "Starting Python scripts..."

# Run scripts in parallel
python3 main.py --csv csv/hr1.csv  --generate-review &
python3 main.py --csv csv/hr1copy.csv --generate-review &
python3 main.py --csv csv/hr1copy2.csv --generate-review &
python3 main.py --csv csv/hr1copy3.csv --generate-review &
python3 main.py --csv csv/hr1copy4.csv --generate-review &
python3 main.py --csv csv/hr1copy5.csv --generate-review &
python3 main.py --csv csv/hr1copy6.csv --generate-review &
python3 main.py --csv csv/hr1copy7.csv --generate-review &
python3 main.py --csv csv/hr1copy8.csv  --generate-review &
python3 main.py --csv csv/hr1copy9.csv --generate-review  &


# Wait for all background jobs to finish
wait

echo "All scripts completed."
