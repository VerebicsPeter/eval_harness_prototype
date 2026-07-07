"""Standalone smoke test for MicrosandboxSandboxEnvironment.

Runs the sandbox class directly, with no Inspect eval loop involved, so a
failure here tells you the bug is in the microsandbox wiring itself rather
than in the task/dataset/scorer.
"""

import asyncio

from microsandbox import Sandbox

from libs.sandboxes.sb_microsandbox import MicrosandboxConfig, MicrosandboxSandboxEnvironment


async def main() -> None:
    cfg = MicrosandboxConfig(image="python", cpus=1, memory=512)

    print(f"booting microvm (image={cfg.image}, cpus={cfg.cpus}, memory={cfg.memory}MiB)...")
    
    sb = await Sandbox.create(
        "microsandbox-smoke-test",
        image=cfg.image,
        cpus=cfg.cpus,
        memory=cfg.memory,
        replace=True,
    )
    env = MicrosandboxSandboxEnvironment(sb)

    try:
        print("\n[1/3] exec()")
        result1 = await env.exec(["python3", "-c", "print('hello from microvm')"])
        print("  success:", result1.success)
        print("  stdout: ", result1.stdout.strip())
        assert result1.success, f"exec failed: {result1.stderr}"
        assert "hello from microvm" in result1.stdout

        print("\n[2/3] write_file() + read_file() round trip")
        await env.write_file("/tmp/msg.txt", "round trip works\n")
        result2 = await env.read_file("/tmp/msg.txt")
        print("  read back:", result2.strip())
        assert result2.strip() == "round trip works"

        print("\n[3/3] nonzero exit code is reported correctly")
        result3 = await env.exec(["python3", "-c", "import sys; sys.exit(1)"])
        print("  success:", result3.success)
        print("  returncode:", result3.returncode)
        assert result3.success is False
        assert result3.returncode == 1

        print("\nAll smoke tests passed.")
    finally:
        
        print("\nstopping microvm...")
        await sb.stop()


if __name__ == "__main__":
    asyncio.run(main())