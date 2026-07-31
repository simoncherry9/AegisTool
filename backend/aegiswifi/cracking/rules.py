"""Gestor de reglas de Hashcat (minuta §18).

Escanea directorios en busca de archivos ``.rule``, lee metadatos y
cuenta reglas bajo demanda para informar al :class:`CrackingPlanner`.
"""

from __future__ import annotations

from pathlib import Path

from aegiswifi.cracking.schemas import RuleInfo


class RulesManager:
    """Administra el inventario de reglas de Hashcat disponibles.

    Busca archivos ``.rule`` en uno o más directorios.

    Directorios escaneados por defecto:
      1. ``/usr/share/hashcat/rules/`` (Kali Linux)
      2. ``data/rules/``               (local del proyecto)
    """

    def __init__(self, extra_dirs: list[Path] | None = None) -> None:
        self._dirs: list[Path] = extra_dirs or [
            Path("/usr/share/hashcat/rules"),
            Path("data/rules"),
        ]
        self._cache: dict[str, RuleInfo] = {}

    # ------------------------------------------------------------------
    # Escaneo
    # ------------------------------------------------------------------

    def scan_all(self, force: bool = False) -> list[RuleInfo]:
        """Escanea todos los directorios configurados.

        Args:
            force: Si ``True``, re-escannea aunque ya esté cacheado.

        Returns:
            Lista de :class:`RuleInfo` ordenada por nombre.
        """
        if self._cache and not force:
            return sorted(self._cache.values(), key=lambda r: r.name)

        self._cache.clear()
        seen: set[str] = set()

        for directory in self._dirs:
            if not directory.is_dir():
                continue
            for entry in sorted(directory.iterdir()):
                if not entry.is_file() or entry.suffix.lower() != ".rule":
                    continue

                path_str = str(entry.resolve())
                if path_str in seen:
                    continue
                seen.add(path_str)

                info = RuleInfo(
                    path=path_str,
                    name=entry.name,
                    size_bytes=entry.stat().st_size,
                )
                self._cache[path_str] = info

        return sorted(self._cache.values(), key=lambda r: r.name)

    def get(self, path: str) -> RuleInfo | None:
        """Retorna el info de un archivo de reglas específico.

        Si no está en caché, lo escanea.
        """
        if path in self._cache:
            return self._cache[path]

        p = Path(path)
        if not p.is_file():
            return None

        info = RuleInfo(
            path=str(p.resolve()),
            name=p.name,
            size_bytes=p.stat().st_size,
        )
        self._cache[info.path] = info
        return info

    # ------------------------------------------------------------------
    # Conteo de reglas
    # ------------------------------------------------------------------

    def count_rules(self, path: str, encoding: str = "utf-8") -> int | None:
        """Cuenta la cantidad de reglas en un archivo.

        Una regla por línea (las líneas vacías y comentarios no cuentan).
        """
        p = Path(path)
        if not p.is_file():
            return None

        try:
            count = 0
            with p.open("r", encoding=encoding, errors="replace") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        count += 1
            return count
        except OSError:
            return None
