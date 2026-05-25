"""Copy premium con Anthropic Claude."""

from __future__ import annotations

import json
import logging
import os
import re

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def generate_copy(
    business_name: str,
    reviews: list[str],
    *,
    city: str = "",
    category: str = "Restaurante",
) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Falta ANTHROPIC_API_KEY")
    loc = city or "la zona"
    reviews_block = "\n---\n".join(reviews[:6]) if reviews else "Sin reseñas; tono positivo genérico."

    prompt = f"""Copy para landing premium de "{business_name}" ({category}, {loc}).

Reseñas Google:
{reviews_block}

JSON solo (sin markdown):
{{
  "tagline": "eyebrow corto",
  "hero_em": "subtítulo emotivo máx 12 palabras",
  "hero_text": "2-3 frases vendedoras máx 280 chars",
  "about_title": "2-4 palabras",
  "about_extra": "1 frase ambiente",
  "features": [{{"emoji":"🍕","title":"...","text":"..."}}, ... x3],
  "services": ["Comer en local","Para llevar","Terraza"],
  "whatsapp_intro": "1 frase invitando a WhatsApp"
}}
Español España, premium, sin inventar premios."""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL),
        max_tokens=1200,
        system="Copywriter gastronómico. Solo JSON.",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.65,
    )
    raw = "".join(b.text for b in resp.content if b.type == "text")
    data = _parse_json(raw)

    feats = []
    for i, f in enumerate((data.get("features") or [])[:3]):
        if isinstance(f, dict):
            feats.append({"emoji": f.get("emoji", "✨"), "title": f.get("title", f"P{i+1}"), "text": f.get("text", "")})
        else:
            feats.append({"emoji": "✨", "title": f"Punto {i+1}", "text": str(f)})
    while len(feats) < 3:
        feats.append({"emoji": "✨", "title": "Calidad", "text": "Producto fresco cada día."})

    svc = data.get("services") or ["Comer en el local", "Para llevar"]
    return {
        "tagline": str(data.get("tagline") or f"{category} · {loc}"),
        "hero_em": str(data.get("hero_em") or "Sabor auténtico"),
        "hero_text": str(data.get("hero_text") or f"Descubre {business_name}."),
        "about_title": str(data.get("about_title") or "con alma local"),
        "about_extra": str(data.get("about_extra") or ""),
        "features": feats,
        "services": [str(s) for s in svc][:5],
        "whatsapp_intro": str(data.get("whatsapp_intro") or "Escríbenos por WhatsApp."),
    }


def generate_copy_peluqueria(
    business_name: str,
    reviews: list[str],
    *,
    city: str = "",
) -> dict:
    """Copy para peluquería / salón de belleza."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Falta ANTHROPIC_API_KEY")
    loc = city or "Sitges"
    reviews_block = "\n---\n".join(reviews[:6]) if reviews else "Sin reseñas; tono elegante y cercano."

    prompt = f"""Copy para landing de PELEURERÍA / SALÓN "{business_name}" en {loc}.

Reseñas Google:
{reviews_block}

JSON solo:
{{
  "tagline": "eyebrow ej: Peluquería · Sitges · Estilo",
  "hero_em": "subtítulo elegante máx 12 palabras",
  "hero_text": "2-3 frases sobre corte, color, cuidado capilar, máx 280 chars",
  "about_title": "2-4 palabras ej: tu estilo, nuestra pasión",
  "about_extra": "1 frase sobre ambiente del salón",
  "features": [{{"emoji":"✂️","title":"...","text":"..."}}, {{"emoji":"💇","title":"...","text":"..."}}, {{"emoji":"✨","title":"...","text":"..."}}],
  "services": ["Corte mujer","Coloración","Peinado eventos","Tratamientos","Barbería"],
  "whatsapp_intro": "1 frase para reservar cita por WhatsApp"
}}
Español España, tono premium de salón, sin inventar premios."""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL),
        max_tokens=1200,
        system="Copywriter de salones de belleza. Solo JSON.",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.65,
    )
    raw = "".join(b.text for b in resp.content if b.type == "text")
    data = _parse_json(raw)

    feats = []
    for i, f in enumerate((data.get("features") or [])[:3]):
        if isinstance(f, dict):
            feats.append({
                "emoji": f.get("emoji", ["✂️", "💇", "✨"][i]),
                "title": f.get("title", f"Servicio {i+1}"),
                "text": f.get("text", ""),
            })
        else:
            feats.append({"emoji": ["✂️", "💇", "✨"][i], "title": f"Punto {i+1}", "text": str(f)})
    while len(feats) < 3:
        feats.append({"emoji": "✨", "title": "Estilo", "text": "Asesoramiento personalizado."})

    svc = data.get("services") or ["Corte", "Color", "Peinado"]
    return {
        "tagline": str(data.get("tagline") or f"Peluquería · {loc}"),
        "hero_em": str(data.get("hero_em") or "Tu mejor versión empieza aquí"),
        "hero_text": str(data.get("hero_text") or f"En {business_name} cuidamos tu imagen con estilo y dedicación."),
        "about_title": str(data.get("about_title") or "tu estilo"),
        "about_extra": str(data.get("about_extra") or ""),
        "features": feats,
        "services": [str(s) for s in svc][:5],
        "whatsapp_intro": str(data.get("whatsapp_intro") or "Reserva tu cita por WhatsApp en segundos."),
    }


def generate_copy_relojeria(
    business_name: str,
    reviews: list[str],
    *,
    city: str = "",
) -> dict:
    """Copy para relojería / joyería."""
    return _generate_sector_copy(
        business_name,
        reviews,
        city=city or "Barcelona",
        sector="RELOJERÍA / JOYERÍA",
        system="Copywriter de relojerías de lujo. Solo JSON.",
        defaults={
            "tagline": f"Relojería · {city or 'Barcelona'} · Precisión",
            "hero_em": "Cada segundo, una obra de arte",
            "hero_text": f"En {business_name} encontrarás relojes seleccionados y asesoramiento experto.",
            "about_title": "tradición y precisión",
            "features": [
                {"emoji": "⌚", "title": "Relojes seleccionados", "text": "Marcas y modelos para cada estilo."},
                {"emoji": "🔧", "title": "Servicio técnico", "text": "Revisión, pilas y ajustes con cuidado."},
                {"emoji": "✨", "title": "Asesoramiento", "text": "Te ayudamos a elegir el reloj perfecto."},
            ],
            "services": ["Relojes de pulsera", "Relojes de pared", "Baterías y revisiones", "Compra y venta", "Joyas"],
            "whatsapp_intro": "Escríbenos para consultar disponibilidad o pedir cita en tienda.",
        },
        feature_emojis=["⌚", "🔧", "✨"],
    )


def generate_copy_estetica(
    business_name: str,
    reviews: list[str],
    *,
    city: str = "",
) -> dict:
    """Copy para centro de estética / bienestar."""
    return _generate_sector_copy(
        business_name,
        reviews,
        city=city or "Barcelona",
        sector="CENTRO DE ESTÉTICA / BIENESTAR",
        system="Copywriter de centros de estética y spa. Solo JSON.",
        defaults={
            "tagline": f"Estética · {city or 'Barcelona'} · Bienestar",
            "hero_em": "Tu piel, tu momento",
            "hero_text": f"En {business_name} cuidamos tu imagen con tratamientos personalizados y un ambiente de calma.",
            "about_title": "bienestar real",
            "features": [
                {"emoji": "✨", "title": "Tratamientos faciales", "text": "Protocolos adaptados a tu piel."},
                {"emoji": "💆", "title": "Cuerpo y relax", "text": "Sesiones para desconectar y renovarte."},
                {"emoji": "🌿", "title": "Atención cercana", "text": "Profesionales que te asesoran sin prisas."},
            ],
            "services": ["Facial", "Corporal", "Depilación", "Manicura", "Masajes", "Medicina estética"],
            "whatsapp_intro": "Reserva tu cita por WhatsApp y te confirmamos al momento.",
        },
        feature_emojis=["✨", "💆", "🌿"],
    )


def _generate_sector_copy(
    business_name: str,
    reviews: list[str],
    *,
    city: str,
    sector: str,
    system: str,
    defaults: dict,
    feature_emojis: list[str],
) -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("Falta ANTHROPIC_API_KEY")
    reviews_block = "\n---\n".join(reviews[:6]) if reviews else "Sin reseñas; tono premium y cercano."

    prompt = f"""Copy para landing de {sector} "{business_name}" en {city}.

Reseñas Google:
{reviews_block}

JSON solo:
{{
  "tagline": "eyebrow corto",
  "hero_em": "subtítulo máx 12 palabras",
  "hero_text": "2-3 frases vendedoras máx 280 chars",
  "about_title": "2-4 palabras",
  "about_extra": "1 frase ambiente",
  "features": [{{"emoji":"...","title":"...","text":"..."}}, ... x3],
  "services": ["...", "...", "..."],
  "whatsapp_intro": "1 frase invitando a WhatsApp"
}}
Español España, premium, sin inventar premios."""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL),
        max_tokens=1200,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.65,
    )
    raw = "".join(b.text for b in resp.content if b.type == "text")
    data = _parse_json(raw)

    feats = []
    for i, f in enumerate((data.get("features") or [])[:3]):
        if isinstance(f, dict):
            feats.append({
                "emoji": f.get("emoji", feature_emojis[i % len(feature_emojis)]),
                "title": f.get("title", f"Punto {i+1}"),
                "text": f.get("text", ""),
            })
        else:
            feats.append({"emoji": feature_emojis[i % len(feature_emojis)], "title": f"Punto {i+1}", "text": str(f)})
    while len(feats) < 3:
        d = defaults["features"][len(feats)] if len(defaults.get("features", [])) > len(feats) else {
            "emoji": feature_emojis[len(feats) % len(feature_emojis)],
            "title": "Calidad",
            "text": "Atención personalizada.",
        }
        feats.append(d)

    svc = data.get("services") or defaults.get("services", [])
    return {
        "tagline": str(data.get("tagline") or defaults["tagline"]),
        "hero_em": str(data.get("hero_em") or defaults["hero_em"]),
        "hero_text": str(data.get("hero_text") or defaults["hero_text"]),
        "about_title": str(data.get("about_title") or defaults["about_title"]),
        "about_extra": str(data.get("about_extra") or ""),
        "features": feats,
        "services": [str(s) for s in svc][:6],
        "whatsapp_intro": str(data.get("whatsapp_intro") or defaults["whatsapp_intro"]),
    }


def _parse_json(raw: str) -> dict:
    t = raw.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", t)
    if m:
        t = m.group(1).strip()
    return json.loads(t)
