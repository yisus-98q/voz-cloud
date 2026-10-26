import numpy as np
import sounddevice as sd

print("=== Dispositivos de entrada ===")
for i, d in enumerate(sd.query_devices()):
    if d["max_input_channels"] > 0:
        mark = " <-- DEFAULT" if i == sd.default.device[0] else ""
        print(f"  [{i}] {d['name']} (canales={d['max_input_channels']}){mark}")

dur = 4
sr = 16000
print(f"\n=== Grabando {dur}s del micrófono por defecto (habla ahora) ===")
audio = sd.rec(int(dur * sr), samplerate=sr, channels=1, dtype="float32")
sd.wait()
audio = audio.flatten()
rms = float(np.sqrt(np.mean(audio ** 2)))
print(f"RMS promedio: {rms:.5f}  (umbral ENERGY_THRESHOLD=0.01)")
print(f"Máximo: {float(np.max(np.abs(audio))):.5f}")

from faster_whisper import WhisperModel
model = WhisperModel("small", device="cpu", compute_type="int8")

print("\n--- Con VAD (como el sistema) ---")
segs, info = model.transcribe(audio, language="es")
texto = "".join(s.text for s in segs).strip()
print(f"Texto: '{texto}'")

print("\n--- Sin VAD ---")
segs2, _ = model.transcribe(audio, language="es", vad_filter=False)
texto2 = "".join(s.text for s in segs2).strip()
print(f"Texto: '{texto2}'")

np.save(r"D:\voz-cloud\ultima_grabacion.npy", audio)
