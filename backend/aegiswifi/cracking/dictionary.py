"""Gestor de diccionarios/wordlists para Hashcat (minuta §18).

Escanea directorios en busca de wordlists, lee metadatos y cuenta líneas
bajo demanda para informar al :class:`CrackingPlanner`.
"""

from __future__ import annotations

from pathlib import Path

from aegiswifi.cracking.schemas import DictionaryInfo


class DictionaryManager:
    """Administra el inventario de wordlists disponibles.

    Busca archivos de wordlist en uno o más directorios, indexa metadatos
    básicos (tamaño, nombre) y permite contar líneas bajo demanda.

    Directorios escaneados por defecto (en orden):
      1. ``/usr/share/wordlists/`` (Kali Linux)
      2. ``/usr/share/dict/``     (alternativa UNIX)
      3. ``data/wordlists/``      (local del proyecto)
    """

    # Extensiones consideradas wordlist.
    WORDLIST_EXTENSIONS = {".txt", ".lst", ".dic", ".wordlist", ".gz", ".7z"}

    def __init__(self, extra_dirs: list[Path] | None = None) -> None:
        self._dirs: list[Path] = extra_dirs or [
            Path("/usr/share/wordlists"),
            Path("/usr/share/dict"),
            Path("data/wordlists"),
        ]
        self._cache: dict[str, DictionaryInfo] = {}

    # ------------------------------------------------------------------
    # Escaneo
    # ------------------------------------------------------------------

    def scan_all(self, force: bool = False) -> list[DictionaryInfo]:
        """Escanea todos los directorios configurados.

        Args:
            force: Si ``True``, re-escannea aunque ya esté cacheado.

        Returns:
            Lista de :class:`DictionaryInfo` ordenada por nombre.
        """
        if self._cache and not force:
            return sorted(self._cache.values(), key=lambda d: d.name)

        self._cache.clear()
        seen: set[str] = set()

        for directory in self._dirs:
            if not directory.is_dir():
                continue
            for entry in sorted(directory.iterdir()):
                if not entry.is_file():
                    continue
                ext = entry.suffix.lower()
                if ext not in self.WORDLIST_EXTENSIONS and entry.suffix == "":
                    # Archivos sin extensión también pueden ser wordlists.
                    pass
                elif ext not in self.WORDLIST_EXTENSIONS:
                    continue

                path_str = str(entry.resolve())
                if path_str in seen:
                    continue
                seen.add(path_str)

                info = DictionaryInfo(
                    path=path_str,
                    name=entry.name,
                    size_bytes=entry.stat().st_size,
                    is_sorted="sorted" in entry.name.lower() or "rockyou" in entry.name.lower(),
                )
                self._cache[path_str] = info

        return sorted(self._cache.values(), key=lambda d: d.name)

    def get(self, path: str) -> DictionaryInfo | None:
        """Retorna el info de una wordlist específica.

        Si no está en caché, la escanea.
        """
        if path in self._cache:
            return self._cache[path]

        p = Path(path)
        if not p.is_file():
            return None

        info = DictionaryInfo(
            path=str(p.resolve()),
            name=p.name,
            size_bytes=p.stat().st_size,
        )
        self._cache[info.path] = info
        return info

    def create_custom_wordlist(self, name: str, words_list: list[str]) -> DictionaryInfo:
        """Crea una wordlist local sin permitir escapar del directorio administrado."""
        safe_name = Path(name).name.strip()
        if safe_name.lower().endswith(".txt"):
            safe_name = safe_name[:-4]
        if not safe_name or safe_name in {".", ".."}:
            raise ValueError("nombre de diccionario inválido")

        directory = Path("data/wordlists")
        directory.mkdir(parents=True, exist_ok=True)
        file_path = directory / f"{safe_name}.txt"
        if file_path.exists():
            raise FileExistsError(f"el diccionario '{safe_name}' ya existe")

        normalized = [word.strip() for word in words_list if word.strip()]
        file_path.write_text("\n".join(normalized) + "\n", encoding="utf-8")
        info = DictionaryInfo(
            path=str(file_path.resolve()),
            name=file_path.name,
            size_bytes=file_path.stat().st_size,
            line_count=len(normalized),
        )
        self._cache[info.path] = info
        return info

    def delete_custom_wordlist(self, name: str) -> bool:
        """Elimina únicamente wordlists dentro del directorio local administrado."""
        safe_name = Path(name).name
        if not safe_name.lower().endswith(".txt"):
            safe_name += ".txt"
        directory = Path("data/wordlists").resolve()
        file_path = (directory / safe_name).resolve()
        if file_path.parent != directory or not file_path.is_file():
            return False
        file_path.unlink()
        self._cache.pop(str(file_path), None)
        return True

    # ------------------------------------------------------------------
    # Conteo de líneas
    # ------------------------------------------------------------------

    def count_lines(self, path: str, encoding: str = "utf-8") -> int | None:
        """Cuenta las líneas de una wordlist.

        Para archivos .gz, delega en ``zcat``.
        Para .7z, delega en ``7z``.
        """
        p = Path(path)
        if not p.is_file():
            return None

        ext = p.suffix.lower()

        try:
            if ext == ".gz":
                return self._count_gz(p)
            elif ext == ".7z":
                return self._count_7z(p)
            else:
                return self._count_text(p, encoding)
        except (OSError, RuntimeError):
            return None

    def _count_text(self, path: Path, encoding: str = "utf-8") -> int:
        """Cuenta líneas de un archivo de texto plano."""
        count = 0
        with path.open("r", encoding=encoding, errors="replace") as f:
            for _ in f:
                count += 1
        return count

    def _count_gz(self, path: Path) -> int:
        """Cuenta líneas de un .gz usando ``zcat``."""
        import subprocess

        result = subprocess.run(
            ["zcat", str(path)],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError("zcat failed")
        return len(result.stdout.decode("utf-8", errors="replace").splitlines())

    def _count_7z(self, path: Path) -> int:
        """Cuenta líneas de un .7z usando ``7z``."""
        import subprocess

        result = subprocess.run(
            ["7z", "x", "-so", str(path)],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError("7z failed")
        return len(result.stdout.decode("utf-8", errors="replace").splitlines())


def scan_system_wordlists() -> list[str]:
    """Scans /usr/share/wordlists/ for .txt and .lst files."""
    paths = []
    base = Path("/usr/share/wordlists")
    if base.is_dir():
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".txt", ".lst"):
                paths.append(str(p.resolve()))
    return sorted(paths)


def list_all_wordlists() -> list[str]:
    """Combines system + custom wordlists."""
    system = scan_system_wordlists()
    custom = []
    custom_dir = Path("data/wordlists")
    if custom_dir.is_dir():
        for p in custom_dir.rglob("*.txt"):
            custom.append(str(p.resolve()))
    return sorted(system + custom)
