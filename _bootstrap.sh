#!/bin/bash
set -e

# Check for root user
echo "You are `whoami`"
echo ""
if [[ $EUID -eq 0 ]]; then
    echo "Should not be executed as root!"
    exit 1
fi

# Go in the directory of this batch file
cd $(dirname $(realpath $0))

# Test python version. Python 3.4 is too old. Try 3.7 instead
PYTHON=/usr/bin/python3
python_version=`$PYTHON -c 'import sys; print(sys.version_info[0:2])'`
if [ "$python_version" == '(3, 4)' ]; then
        echo
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "! $PYTHON is 3.4... Trying to use python3.7 instead"
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo
        PYTHON=/usr/bin/python3.7
fi

# Setup $VENV variable for both Linux and Windows.
function setupVenv
{
        if [ -e $(dirname $(realpath $0))/venv/bin/python ]; then
                VENV=$(dirname $(realpath $0))/venv/bin
        else
                VENV=$(dirname $(realpath $0))/venv/Scripts
        fi
}

# Prepare virtual environment if needed
if [ ! -e $(dirname $(realpath $0))/venv/.installed ]; then
        if [ -e $(dirname $(realpath $0))/venv ]; then
                echo "Intermediate venv installation found. Cleaning up".
                rm -rf $(dirname $(realpath $0))/venv
        fi
    $PYTHON -m venv $(dirname $(realpath $0))/venv
        setupVenv
    $VENV/python -m pip install setuptools==41.2.0 wheel==0.33.6
    touch $(dirname $(realpath $0))/venv/.installed
else
        setupVenv
fi

$VENV/python -m pip install -r requirements.txt
echo "*****************************************************************************************"
echo "* AT STARTUP THE TOOL PARSES ALL BRANCHES. AT MAY TAKE A WHILE!                         *"
echo "*****************************************************************************************"
echo "* To show the list of protected branches: http://127.0.0.1:6002/branch_protection/list  *"
echo "* To force applying rules: http://127.0.0.1:6002/branch_protection/force_push_list      *"
echo "*****************************************************************************************"
echo ""
$VENV/python -m flask run --host=0.0.0.0 --port=6002
