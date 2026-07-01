import json
import httpx
import asyncio

PISTON_HOST= "http://localhost:2000"


def install_runtime():
    url = f"{PISTON_HOST}/api/v2/packages"
    payload = {"language": "python", "version": "3.10.0"}
    
    try:
        response = httpx.post(url, json=payload, timeout=600.0)
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text}")
    except Exception as e:
        print(f"Network Error: {e}")

def get_runtimes(installed):
    url = f"{PISTON_HOST}/api/v2/packages"
    result = httpx.get(url)
    result = result.json()
    if installed:
        result = [r for r in result if r.get("installed")]
    return result


if __name__ == "__main__":
    # install python 3.10
    install_runtime()
    print(json.dumps(get_runtimes(installed=True), indent=2))
