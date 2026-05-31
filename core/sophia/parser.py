"""
SOPHIA ∞ — Serial Parser
Lê o Serial do ESP32 linha a linha e classifica cada mensagem.
Suporta: [EVENT], [TELEMETRY], [AUDIO], [PIEZO], [STATE_CHANGED], raw
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LineType(Enum):
    EVENT      = "EVENT"
    TELEMETRY  = "TELEMETRY"
    AUDIO      = "AUDIO"
    PIEZO      = "PIEZO"
    STATE      = "STATE"
    SYSTEM     = "SYSTEM"
    UNKNOWN    = "UNKNOWN"


@dataclass
class ParsedLine:
    type:    LineType
    raw:     str
    data:    dict = field(default_factory=dict)
    error:   Optional[str] = None


# Padrões do firmware SOPHIA
_PATTERNS = {
    LineType.EVENT:     re.compile(r'^\[EVENT\]\s+(\{.+\})$'),
    LineType.TELEMETRY: re.compile(r'^\[TELEMETRY\]\s+(\{.+\})$'),
    LineType.AUDIO:     re.compile(r'^\[AUDIO\]'),
    LineType.PIEZO:     re.compile(r'^\[PIEZO\]'),
    LineType.SYSTEM:    re.compile(
        r'^\[(DISPLAY|SENSOR|SOPHIA|STATE|CAL|NET|POWER)\]'
    ),
}


def parse_line(raw: str) -> ParsedLine:
    line = raw.strip()
    if not line:
        return ParsedLine(type=LineType.UNKNOWN, raw=line)

    # EVENT — JSON completo
    m = _PATTERNS[LineType.EVENT].match(line)
    if m:
        try:
            data = json.loads(m.group(1))
            # STATE_CHANGED é um evento especial — também registra como estado
            ltype = LineType.STATE if data.get("event") == "STATE_CHANGED" \
                    else LineType.EVENT
            return ParsedLine(type=ltype, raw=line, data=data)
        except json.JSONDecodeError as e:
            return ParsedLine(type=LineType.EVENT, raw=line,
                              error=f"JSON inválido: {e}")

    # TELEMETRY — JSON completo
    m = _PATTERNS[LineType.TELEMETRY].match(line)
    if m:
        try:
            data = json.loads(m.group(1))
            return ParsedLine(type=LineType.TELEMETRY, raw=line, data=data)
        except json.JSONDecodeError as e:
            return ParsedLine(type=LineType.TELEMETRY, raw=line,
                              error=f"JSON inválido: {e}")

    # AUDIO — parse campos
    if _PATTERNS[LineType.AUDIO].match(line):
        data = _parse_audio(line)
        return ParsedLine(type=LineType.AUDIO, raw=line, data=data)

    # PIEZO — parse campos
    if _PATTERNS[LineType.PIEZO].match(line):
        data = _parse_piezo(line)
        return ParsedLine(type=LineType.PIEZO, raw=line, data=data)

    # SYSTEM — logs de boot/status
    if _PATTERNS[LineType.SYSTEM].match(line):
        return ParsedLine(type=LineType.SYSTEM, raw=line,
                          data={"message": line})

    return ParsedLine(type=LineType.UNKNOWN, raw=line)


def _parse_audio(line: str) -> dict:
    """
    [AUDIO]  ativo: SIM | int: 0.37 | mov: 0.56 | state: ACTIVE
    """
    data = {}
    try:
        data["ativo"] = "SIM" in line
        m = re.search(r'int:\s*([\d.]+)', line)
        if m: data["intensidade"] = float(m.group(1))
        m = re.search(r'mov:\s*([\d.]+)', line)
        if m: data["mov"] = float(m.group(1))
        m = re.search(r'state:\s*(\w+)', line)
        if m: data["state"] = m.group(1)
    except Exception:
        pass
    return data


def _parse_piezo(line: str) -> dict:
    """
    [PIEZO]  impacto=0.318 LEVE
    """
    data = {}
    try:
        m = re.search(r'impacto=([\d.]+)', line)
        if m: data["intensidade"] = float(m.group(1))
        data["nivel"] = "FORTE" if "FORTE" in line else "LEVE"
    except Exception:
        pass
    return data
