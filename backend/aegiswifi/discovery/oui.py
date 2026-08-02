import asyncio
import logging
import httpx

log = logging.getLogger(__name__)

# Cache en memoria de prefijos OUI a Vendor
_oui_cache: dict[str, str | None] = {}
# Para evitar consultar la misma MAC simultáneamente
_pending_lookups: set[str] = set()

async def get_vendor(mac: str) -> str | None:
    """Obtiene el fabricante de una MAC address.
    Utiliza caché local y, si no existe, consulta de forma asíncrona a un API público.
    """
    if not mac:
        return None
    
    # Normalizar MAC y extraer prefijo OUI (los primeros 3 octetos)
    mac_clean = mac.replace(":", "").replace("-", "").upper()
    if len(mac_clean) < 6:
        return None
    prefix = mac_clean[:6]

    if prefix in _oui_cache:
        return _oui_cache[prefix]
    
    if prefix in _pending_lookups:
        # Ya se está consultando, para no saturar devolvemos None temporalmente
        return None

    _pending_lookups.add(prefix)

    # Disparar tarea en background para no bloquear
    asyncio.create_task(_fetch_vendor_task(prefix))
    return None

async def _fetch_vendor_task(prefix: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(f"https://api.macvendors.com/{prefix}")
            if res.status_code == 200 and res.text:
                _oui_cache[prefix] = res.text.strip()
            else:
                # Si no se encuentra, guardar None para no volver a consultar
                _oui_cache[prefix] = None
    except Exception as e:
        log.debug(f"Error fetching OUI for {prefix}: {e}")
    finally:
        _pending_lookups.discard(prefix)
