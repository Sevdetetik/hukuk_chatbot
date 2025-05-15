import subprocess
import platform

def ping(host):
    # Determine the operating system to use appropriate ping command
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    
    # Construct the ping command
    command = ['ping', param, '1', host]
    
    try:
        # Execute the ping command
        output = subprocess.run(command, capture_output=True, text=True)
        return output.returncode == 0  # Returns True if ping was successful
    except Exception as e:
        print(f"Error occurred: {e}")
        return False

# Example usage
host = "google.com"
if ping(host):
    print(f"{host} is reachable")
else:
    print(f"{host} is not reachable")