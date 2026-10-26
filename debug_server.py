import subprocess, sys, time, os, socket

os.chdir('D:\\voz-cloud')

# Check if port 8080 is already in use
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = s.connect_ex(('127.0.0.1', 8080))
if result == 0:
    print("Port 8080 is already in use!")
else:
    print("Port 8080 is available")

s.close()

# Start server
print("Starting server...")
proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8080'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)

# Wait for startup
time.sleep(5)

# Check if process is still alive
poll = proc.poll()
print(f"Process poll result: {poll}")

if poll is None:
    # Process is still running, try to connect
    print("Server process is running, testing connection...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = s.connect_ex(('127.0.0.1', 8080))
    if result == 0:
        print("Connection successful! Port 8080 is open.")
        s.close()
    else:
        print(f"Connection failed with code: {result}")
        s.close()
else:
    # Process died, get error output
    print(f"Server process died immediately. Exit code: {poll}")
    stdout, stderr = proc.communicate()
    print(f"Stdout: {stdout.decode('utf-8', errors='ignore')[-500:]}")
    print(f"Stderr: {stderr.decode('utf-8', errors='ignore')[-500:]}")