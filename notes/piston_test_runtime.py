import json
import httpx
import asyncio

PISTON_HOST= "http://localhost:2000"


def run_py_code_in_3_10_runtime(py_source_files: list[str], py_assert_stmts: str):
    url = f"{PISTON_HOST}/api/v2/execute"
    
    files = list(
        map(
            lambda snip: {"content": '\n'.join((snip, py_assert_stmts))},
            py_source_files
        )
    )
    
    payload = {
        "language": "python",
        "version": "3.10.0",
        "files": files
    }
    
    try:
        response = httpx.post(url, json=payload, timeout=30.0)
        response = response.json()
        return response
    except Exception as e:
        print(f"Network Error: {e}")


if __name__ == "__main__":
    result = run_py_code_in_3_10_runtime(
        # NOTE: when passing many files it does not test everythin one by one, only tests the first file, the other files serve as 'implementation detail'...
        py_source_files=[
            #"while True: pass",  # infinite
            "def is_even(n): return n%2==1",  # bad
            "def is_even(n): return n%2==0",  # good
        ],
        py_assert_stmts="assert is_even(4)==True; assert is_even(5)==False; assert is_even(420)==True; assert is_even(0)==True"
    )
    print(json.dumps(result, indent=2))
