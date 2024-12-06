#!/bin/bash
cd /home/ubuntu/Farm-Code           # Local path to your cloned repository
git pull origin main                # Pull the latest changes from GitHub
sudo systemctl restart gunicorn     # Restart the Gunicorn service (or whatever you're using)
