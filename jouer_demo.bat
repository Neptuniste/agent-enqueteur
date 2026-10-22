@echo off
rem Lance « Les Dossiers de l'Inspecteur » en mode démo (sans modèle ni GPU) dans le navigateur.
rem La première fois, crée .venv et y installe Gradio, seul paquet nécessaire au mode démo.
rem Pour jouer avec le vrai modèle, il faut un GPU : voir jouer.ipynb (Colab) ou « python jouer.py --help ».
chcp 65001 >nul
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if exist "%PY%" goto :gradio
echo Première utilisation : création de l'environnement .venv…
py -3 -m venv .venv 2>nul || python -m venv .venv
if not exist "%PY%" goto :sans_python
:gradio
"%PY%" -c "import gradio" 2>nul && goto :jouer
echo Installation de Gradio, une seule fois (une à deux minutes)…
"%PY%" -m pip install -q --disable-pip-version-check gradio==6.30.0 || goto :echec
:jouer
"%PY%" jouer.py --demo %*
pause
exit /b

:sans_python
echo Python est introuvable. Installez Python 3.10 à 3.13 depuis https://www.python.org/downloads/
echo en cochant « Add python.exe to PATH », puis relancez ce fichier.
pause
exit /b 1

:echec
echo L'installation de Gradio a échoué : vérifiez la connexion Internet, puis relancez ce fichier.
pause
exit /b 1
