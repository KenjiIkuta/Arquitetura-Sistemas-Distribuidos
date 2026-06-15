@echo off
echo Abra 4 terminais na pasta do projeto e execute:
echo.
echo Terminal 1 - Master B:
echo python master.py --master-id B --host 127.0.0.1 --port 8001 --capacity 10 --release-threshold 3 --seed-tasks 0 --neighbor A=127.0.0.1:8000
echo.
echo Terminal 2 - Master A saturado:
echo python master.py --master-id A --host 127.0.0.1 --port 8000 --capacity 3 --release-threshold 1 --seed-tasks 12 --neighbor B=127.0.0.1:8001
echo.
echo Terminal 3 - Worker B1:
echo python worker.py --worker-id B1 --master-id B --master-address 127.0.0.1:8001 --command-port 9101
echo.
echo Terminal 4 - Worker B2:
echo python worker.py --worker-id B2 --master-id B --master-address 127.0.0.1:8001 --command-port 9102
echo.
pause
