"""
SOPHIA ∞ — Qwen Bridge
Conecta o Observer Engine ao Qwen2.5-Coder via Ollama API local.

Fluxo:
  SessionSnapshot → prompt → Qwen → resposta → ação
"""

import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional
from .observer import SessionSnapshot, snapshot_to_prompt


# ── Config ────────────────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL      = "qwen2.5-coder:7b"
TIMEOUT_S  = 30


# ── Resposta estruturada ──────────────────────────────────────────────────

@dataclass
class SophiaInsight:
    nivel:     str        # BAIXO | MODERADO | ALTO | CRITICO
    padrao:    str        # padrão detectado
    insight:   str        # análise em linguagem natural
    sugestao:  str        # ação recomendada
    oled_msg:  str        # mensagem curta para o OLED (max 20 chars)
    raw:       str = ""   # resposta bruta do Qwen


# ── System prompt ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Você é SOPHIA ∞, um sistema cognitivo embarcado que analisa 
dados de sensores IoT (movimento, áudio, vibração) e gera insights contextuais.

Responda SEMPRE em JSON válido com exatamente esta estrutura:
{
  "insight": "análise em 1-2 frases do que está acontecendo",
  "sugestao": "ação ou observação recomendada em 1 frase",
  "oled_msg": "mensagem de até 20 caracteres para display OLED"
}

Seja direto, prático e útil. Não use markdown. Apenas JSON."""


# ── Bridge ────────────────────────────────────────────────────────────────

class QwenBridge:

    def __init__(self, model: str = MODEL, url: str = OLLAMA_URL):
        self.model = model
        self.url   = url

    # ── API pública ───────────────────────────────────────────────────────

    def analyze(self, snap: SessionSnapshot) -> SophiaInsight:
        """Envia snapshot para o Qwen e retorna insight estruturado."""
        prompt = snapshot_to_prompt(snap)
        raw    = self._call_ollama(prompt)

        if raw is None:
            return self._fallback(snap)

        return self._parse_response(raw, snap)

    def ping(self) -> bool:
        """Verifica se o Ollama está rodando."""
        try:
            req = urllib.request.Request(
                "http://localhost:11434/api/tags",
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status == 200
        except Exception:
            return False

    # ── Ollama call ───────────────────────────────────────────────────────

    def _call_ollama(self, prompt: str) -> Optional[str]:
        payload = json.dumps({
            "model":  self.model,
            "prompt": prompt,
            "system": SYSTEM_PROMPT,
            "stream": False,
            "options": {
                "temperature": 0.3,   # mais determinístico para IoT
                "num_predict": 200,
            }
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                self.url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                data = json.loads(r.read().decode("utf-8"))
                return data.get("response", "")
        except urllib.error.URLError as e:
            print(f"[QWEN] Ollama indisponível: {e}")
            return None
        except Exception as e:
            print(f"[QWEN] Erro na chamada: {e}")
            return None

    # ── Parse ─────────────────────────────────────────────────────────────

    def _parse_response(self, raw: str, snap: SessionSnapshot) -> SophiaInsight:
        """Extrai JSON da resposta do Qwen."""
        try:
            # Remove possível markdown fence
            text = raw.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]

            data = json.loads(text.strip())

            return SophiaInsight(
                nivel    = snap.nivel_geral,
                padrao   = snap.padrao,
                insight  = data.get("insight", snap.resumo),
                sugestao = data.get("sugestao", snap.sugestao),
                oled_msg = data.get("oled_msg", snap.nivel_geral)[:20],
                raw      = raw,
            )
        except (json.JSONDecodeError, KeyError) as e:
            print(f"[QWEN] Parse falhou ({e}) — usando fallback semântico")
            return self._fallback(snap, raw)

    def _fallback(self, snap: SessionSnapshot, raw: str = "") -> SophiaInsight:
        """Fallback quando Qwen não responde — usa Observer diretamente."""
        oled_map = {
            "CRITICO":  "ALERTA CRITICO",
            "ALTO":     "ATIVIDADE ALTA",
            "MODERADO": "ATIVO",
            "BAIXO":    "IDLE",
        }
        return SophiaInsight(
            nivel    = snap.nivel_geral,
            padrao   = snap.padrao,
            insight  = snap.resumo,
            sugestao = snap.sugestao,
            oled_msg = oled_map.get(snap.nivel_geral, "SOPHIA"),
            raw      = raw,
        )