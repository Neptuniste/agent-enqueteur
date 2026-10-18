@echo off
rem Lance « Les Dossiers de l'Inspecteur » en mode démo (sans modèle ni GPU) dans le navigateur.
rem Pour jouer avec le vrai modèle, il faut un GPU : voir jouer.ipynb (Colab) ou « python jouer.py --help ».
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" jouer.py --demo
) else (
  python jouer.py --demo
)
pause
