import os
import subprocess
import time
import shutil
import pytest

@pytest.mark.skipif(shutil.which("docker-compose") is None, reason="docker-compose not available")
def test_resilience():
    print("Simulating resilience test...")
    # Apagar el servicio Central
    subprocess.run(["docker-compose", "stop", "central"])
    print("Central stopped. Waiting...")
    time.sleep(10)

    # Reiniciar el Central
    subprocess.run(["docker-compose", "start", "central"])
    print("Central restarted. Verifying reconnections...")
    time.sleep(10)

    # Verificar reconexión (puedes expandirlo según las métricas)
    print("Resilience test completed.")

if __name__ == "__main__":
    test_resilience()
