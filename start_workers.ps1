$workers = 4
echo "🚀 Starting $workers Worker Instances..."

for ($i=1; $i -le $workers; $i++) {
    echo "   Starting Worker #$i..."
    Start-Process python -ArgumentList "worker.py" -WorkingDirectory "c:\laragon\www\collectordata"
}

echo "✅ All workers started in background windows."
