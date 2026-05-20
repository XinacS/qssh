@echo off
cd /d %~dp0
python -m qssh.flush
python -m qssh.stop
