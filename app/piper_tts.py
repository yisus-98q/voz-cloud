import os
import subprocess
import tempfile
import sys
import logging
import threading

logging.basicConfig(filename=r'D:\voz-cloud\tts_errors.log', level=logging.DEBUG, force=True)

PIPER_EXE = os.getenv("PIPER_EXE", r"C:\piper\piper\piper.exe")
PIPER_MODEL = os.getenv("PIPER_MODEL", r"C:\piper\piper\es_ES-davefx-medium.onnx")

# Lock para evitar reproducciones simultáneas
_speak_lock = threading.Lock()


def speak(text: str) -> None:
    """Sintetiza texto con Piper y lo reproduce por voz."""
    with _speak_lock:
        fd, wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            result = subprocess.run(
                [PIPER_EXE, "--model", PIPER_MODEL, "--output_file", wav],
                input=text.encode("utf-8"),
                check=True,
                timeout=30,
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logging.debug(f"WAV generado: {wav} ({os.path.getsize(wav)} bytes)")

            # Crear un script PowerShell temporal para reproducir con MediaPlayer
            ps_script_path = wav + ".ps1"
            with open(ps_script_path, "w", encoding="utf-8") as f:
                f.write("Add-Type -AssemblyName PresentationCore\n")
                f.write("$player = New-Object System.Windows.Media.MediaPlayer\n")
                f.write(f'$player.Open([System.Uri]::new(\"{wav}\"))\n')
                f.write("$player.Play()\n")
                f.write("Start-Sleep -Seconds 5\n")
                f.write("$player.Close()\n")

            # Ejecutar el script PowerShell
            r = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_script_path],
                creationflags=flags,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            logging.debug(f"PowerShell stdout: {r.stdout.decode()}")
            logging.debug(f"PowerShell stderr: {r.stderr.decode()}")
            logging.debug(f"PowerShell returncode: {r.returncode}")

            # Fallback: winsound
            if r.returncode != 0:
                logging.warning("PowerShell falló, usando winsound")
                import winsound
                winsound.PlaySound(wav, winsound.SND_FILENAME)

        except Exception as e:
            logging.error(f"Error en speak: {e}")
            # Fallback: winsound
            try:
                import winsound
                winsound.PlaySound(wav, winsound.SND_FILENAME)
            except Exception as e2:
                logging.error(f"Error en winsound fallback: {e2}")
        finally:
            try:
                os.remove(wav)
            except OSError:
                pass
            try:
                os.remove(ps_script_path)
            except OSError:
                pass
