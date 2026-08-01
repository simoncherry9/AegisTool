from __future__ import annotations

import asyncio
from typing import Any

from aegiswifi.adapters.base import ToolAdapter
from aegiswifi.adapters.registry import register_adapter

class JohnAdapter(ToolAdapter):
    tool_name = "john"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._cracked_password: str | None = None

    async def get_version(self) -> str:
        proc = await asyncio.create_subprocess_exec(
            "john",
            "--list=build-info",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if stdout:
            return stdout.decode("utf-8", errors="replace").split("\n")[0].strip()
        return "john (version unknown)"

    async def build_command(self, options: dict[str, Any]) -> list[str]:
        cmd = ["john", "--format=wpapsk"]
        if dict_path := options.get("dictionary"):
            cmd.append(f"--wordlist={dict_path}")
            
        hash_file: str = options["hash_file"]
        cmd.append(hash_file)
        return cmd

    async def parse_output(self, line: str) -> dict[str, Any] | None:
        return None

    async def collect_results(self) -> dict[str, Any]:
        options = self._job_parameters.get("options", {})
        hash_file = options.get("hash_file", "")
        proc = await asyncio.create_subprocess_exec(
            "john",
            "--show",
            "--format=wpapsk",
            hash_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        
        password = None
        if stdout:
            text = stdout.decode("utf-8", errors="replace").strip()
            for line in text.split("\n"):
                if ":" in line and not line.startswith("0 password"):
                    parts = line.split(":")
                    if len(parts) >= 2:
                        password = parts[1].strip()
                        break
                        
        cracked = password is not None

        return {
            "cracked": cracked,
            "password": password,
            "exit_code": self._raw_result.get("exit_code"),
            "peak_speed": 0,
            "stages_executed": 1,
            "total_runtime_seconds": self._raw_result.get("runtime_seconds"),
            "log_path": self._raw_result.get("log_path"),
            "sha256": self._raw_result.get("sha256"),
        }

register_adapter("john_crack", JohnAdapter)
