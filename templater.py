"""Render landings premium — plantilla Oliva Garden."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape

from scraper import PlaceLead, ReviewCard

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent
TEMPLATES_DIR = ROOT / "templates"
DIST_DIR = ROOT / "dist"

HERO_IMAGES = [
    "https://images.unsplash.com/photo-1565299624946-b28f40a7ca7b?w=1200&q=85",
    "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=1200&q=85",
    "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=1200&q=85",
    "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=1200&q=85",
]
STORY_IMAGES = [
    "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=700&q=80",
    "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=700&q=80",
    "https://images.unsplash.com/photo-1552566626-52f8b828add9?w=700&q=80",
]

SALON_HERO = [
    "https://images.unsplash.com/photo-1633681926022-9e79c8e4b6e1?w=1400&q=88",
    "https://images.unsplash.com/photo-1522337360788-8a713f999331?w=1400&q=88",
    "https://images.unsplash.com/photo-1560066984-138dadb4c035?w=1400&q=88",
    "https://images.unsplash.com/photo-1521596469430-5f0576834f3e?w=1400&q=88",
]
SALON_STORY = [
    "https://images.unsplash.com/photo-1562322140-8baeececf53d?w=800&q=85",
    "https://images.unsplash.com/photo-1595476108010-bb709967bb25?w=800&q=85",
    "https://images.unsplash.com/photo-1634449577050-7b27a462bc42?w=800&q=85",
]

WATCH_HERO = [
    "https://images.unsplash.com/photo-1523170335258-f5ed11844a49?w=1400&q=88",
    "https://images.unsplash.com/photo-1524593362215-925f3ae4782d?w=1400&q=88",
    "https://images.unsplash.com/photo-1587836374828-4dbafa94d0b7?w=1400&q=88",
    "https://images.unsplash.com/photo-1612817159948-7c77f8a5a6f0?w=1400&q=88",
]
WATCH_STORY = [
    "https://images.unsplash.com/photo-1611591437281-460bfbeff6a0?w=800&q=85",
    "https://images.unsplash.com/photo-1548171915-e79a380a9a0c?w=800&q=85",
    "https://images.unsplash.com/photo-1622431353536-795eccd21d2b?w=800&q=85",
]

ESTETICA_HERO = [
    "https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?w=1400&q=88",
    "https://images.unsplash.com/photo-1515377905743-f9e3f2376c90?w=1400&q=88",
    "https://images.unsplash.com/photo-1616394584738-fc6e612e71b9?w=1400&q=88",
    "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=1400&q=88",
]
ESTETICA_STORY = [
    "https://images.unsplash.com/photo-1512290923902-8a9f81dc236c?w=800&q=85",
    "https://images.unsplash.com/photo-1600334089648-4e0a4a8e7c5e?w=800&q=85",
    "https://images.unsplash.com/photo-1515377905743-f9e3f2376c90?w=800&q=85",
]

# Modelos disponibles para bases / automatización
MODELOS_WEB = {
    "pizzeria": {"plantilla": "index.html", "categoria": "Restaurante / Pizzería"},
    "peluqueria": {"plantilla": "peluqueria.html", "categoria": "Peluquería"},
    "relojeria": {"plantilla": "relojeria.html", "categoria": "Relojería / Joyería"},
    "estetica": {"plantilla": "estetica.html", "categoria": "Centro de estética"},
}


def clean_name(name: str) -> str:
    n = re.sub(r"[\U00010000-\U0010ffff\u2600-\u27BF\uFE0F\u200D]+", "", name).strip()
    return re.sub(r"\s{2,}", " ", n) or name


def phone_href(phone: str) -> str:
    d = re.sub(r"\D", "", phone)
    if len(d) == 9:
        d = "34" + d
    return f"tel:+{d}" if d else "#"


def _wa_digits(phone: str) -> str:
    d = re.sub(r"\D", "", phone or "")
    return "34" + d if len(d) == 9 else d


def has_whatsapp(phone: str) -> bool:
    return len(_wa_digits(phone)) >= 9


def whatsapp_href(phone: str, msg: str) -> str:
    d = _wa_digits(phone)
    return f"https://wa.me/{d}?text={quote(msg, safe='')}" if len(d) >= 9 else "#"


def whatsapp_message_info(name: str) -> str:
    return f"Hola, he visto vuestra página web y me gustaría más información sobre {clean_name(name)}"


def whatsapp_message_order(name: str) -> str:
    return f"Hola, me gustaría hacer un pedido en {clean_name(name)}"


def whatsapp_message_reserve(name: str) -> str:
    return "Hola, quería consultar disponibilidad para reservar mesa"


def whatsapp_message_cita(name: str) -> str:
    return f"Hola, me gustaría pedir cita en {clean_name(name)}"


def whatsapp_message_reloj(name: str) -> str:
    return f"Hola, me gustaría información sobre relojes y disponibilidad en {clean_name(name)}"


def whatsapp_message_estetica(name: str) -> str:
    return f"Hola, me gustaría reservar un tratamiento en {clean_name(name)}"


def salon_hero_image(name: str) -> str:
    i = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(SALON_HERO)
    return SALON_HERO[i]


def salon_story_image(name: str) -> str:
    i = int(hashlib.md5((name + "s").encode()).hexdigest(), 16) % len(SALON_STORY)
    return SALON_STORY[i]


def watch_hero_image(name: str) -> str:
    i = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(WATCH_HERO)
    return WATCH_HERO[i]


def watch_story_image(name: str) -> str:
    i = int(hashlib.md5((name + "w").encode()).hexdigest(), 16) % len(WATCH_STORY)
    return WATCH_STORY[i]


def estetica_hero_image(name: str) -> str:
    i = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(ESTETICA_HERO)
    return ESTETICA_HERO[i]


def estetica_story_image(name: str) -> str:
    i = int(hashlib.md5((name + "e").encode()).hexdigest(), 16) % len(ESTETICA_STORY)
    return ESTETICA_STORY[i]


def stars_display(rating: float) -> str:
    full = int(rating)
    return "★" * full + "☆" * (5 - full)


def review_stars(n: int) -> str:
    return "★" * max(1, min(5, n))


def truncate_review(text: str, max_len: int = 220) -> str:
    text = " ".join(text.split())
    return text if len(text) <= max_len else text[: max_len - 1].rsplit(" ", 1)[0] + "…"


def short_addr(address: str) -> str:
    return address.split(",")[0].strip()


def street_label(address: str) -> str:
    s = short_addr(address)
    return s[:42] if s else "Centro"


def parse_hours(lines: list[str]) -> list[dict]:
    out = []
    for h in lines:
        if ":" in h:
            day, time = h.split(":", 1)
            closed = any(w in time.lower() for w in ("cerrado", "closed"))
            out.append({"day": day.strip(), "time": time.strip(), "open": not closed})
    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    while len(out) < 7:
        out.append({"day": days[len(out) % 7], "time": "12:00 – 23:00", "open": True})
    return out[:7]


def pick_reviews(cards: list[ReviewCard]) -> list[ReviewCard]:
    pos = [c for c in cards if c.stars >= 4]
    sel = (pos if len(pos) >= 2 else cards)[:6]
    return sel or cards[:3]


def hero_image(name: str) -> str:
    i = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(HERO_IMAGES)
    return HERO_IMAGES[i]


def story_image(name: str) -> str:
    i = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(STORY_IMAGES)
    return STORY_IMAGES[i]


def map_embed(address: str) -> str:
    return f"https://maps.google.com/maps?q={quote(address)}&output=embed&z=16"


def render_landing(*, lead: PlaceLead, copy: dict[str, Any], output_dir: Path) -> Path:
    import shutil
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cards = pick_reviews(lead.review_cards) or [
        ReviewCard("Cliente", "CL", 5, t[:220], "Google") for t in lead.reviews[:4]
    ]
    track = cards + cards
    display = clean_name(lead.name)
    meta = f"{display} — {copy.get('hero_em', '')}. {copy.get('hero_text', '')[:100]}"[:160]

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))
    env.filters["truncate_review"] = truncate_review

    html = env.get_template("index.html").render(
        name=lead.name,
        name_clean=display,
        phone=lead.phone or "Consultar",
        address=lead.address,
        short_address=short_addr(lead.address),
        street_label=street_label(lead.address),
        city=lead.city or "Barcelona",
        category=lead.category,
        tagline=copy.get("tagline", ""),
        hero_em=copy.get("hero_em", ""),
        hero_text=copy.get("hero_text", ""),
        about_title=copy.get("about_title", "con alma local"),
        about_extra=copy.get("about_extra", ""),
        features=copy.get("features", []),
        services=copy.get("services", []),
        whatsapp_intro=copy.get("whatsapp_intro", ""),
        meta_description=meta,
        rating=round(lead.rating, 1),
        stars=stars_display(lead.rating),
        review_count=lead.review_count or len(lead.reviews) * 30,
        review_cards=cards,
        carousel_reviews=track,
        hours_rows=parse_hours(lead.opening_hours),
        phone_href=phone_href(lead.phone),
        has_whatsapp=has_whatsapp(lead.phone),
        whatsapp_href=whatsapp_href(lead.phone, whatsapp_message_info(lead.name)),
        whatsapp_hours_href=whatsapp_href(lead.phone, whatsapp_message_reserve(lead.name)),
        whatsapp_order_href=whatsapp_href(lead.phone, whatsapp_message_order(lead.name)),
        hero_image_url=hero_image(lead.name),
        story_image_url=story_image(lead.name),
        map_embed_url=map_embed(lead.address),
        services_count=len(copy.get("services", [])),
        review_stars=review_stars,
        year=__import__("datetime").datetime.now().year,
    )
    out = output_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    logger.info("Landing: %s", out)
    return out.resolve()


def render_peluqueria_landing(*, lead: PlaceLead, copy: dict[str, Any], output_dir: Path) -> Path:
    """Landing peluquería — plantilla peluqueria.html (estilo salón)."""
    import shutil
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cards = pick_reviews(lead.review_cards) or [
        ReviewCard("Cliente", "CL", 5, t[:220], "Google") for t in lead.reviews[:4]
    ]
    track = cards + cards
    display = clean_name(lead.name)
    cat = lead.category if "peluquer" in lead.category.lower() or "salon" in lead.category.lower() or "hair" in lead.category.lower() else "Peluquería"
    meta = f"{display} — Peluquería en {lead.city or 'Sitges'}. {copy.get('hero_text', '')[:80]}"[:160]

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))
    env.filters["truncate_review"] = truncate_review

    html = env.get_template("peluqueria.html").render(
        name=lead.name,
        name_clean=display,
        phone=lead.phone or "Consultar",
        address=lead.address,
        short_address=short_addr(lead.address),
        street_label=street_label(lead.address),
        city=lead.city or "Sitges",
        category=cat,
        tagline=copy.get("tagline", f"Peluquería · {lead.city}"),
        hero_em=copy.get("hero_em", ""),
        hero_text=copy.get("hero_text", ""),
        about_title=copy.get("about_title", "tu estilo"),
        about_extra=copy.get("about_extra", ""),
        features=copy.get("features", []),
        services=copy.get("services", []),
        whatsapp_intro=copy.get("whatsapp_intro", ""),
        meta_description=meta,
        rating=round(lead.rating, 1),
        stars=stars_display(lead.rating),
        review_count=lead.review_count or len(lead.reviews) * 20,
        review_cards=cards,
        carousel_reviews=track,
        hours_rows=parse_hours(lead.opening_hours),
        phone_href=phone_href(lead.phone),
        has_whatsapp=has_whatsapp(lead.phone),
        whatsapp_href=whatsapp_href(lead.phone, whatsapp_message_info(lead.name)),
        whatsapp_hours_href=whatsapp_href(lead.phone, "Hola, quería reservar cita para un servicio de peluquería"),
        whatsapp_order_href=whatsapp_href(lead.phone, whatsapp_message_cita(lead.name)),
        hero_image_url=salon_hero_image(lead.name),
        story_image_url=salon_story_image(lead.name),
        map_embed_url=map_embed(lead.address),
        services_count=len(copy.get("services", [])),
        review_stars=review_stars,
        year=__import__("datetime").datetime.now().year,
    )
    out = output_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    logger.info("Landing peluquería: %s", out)
    return out.resolve()


def _render_salon_style(
    *,
    lead: PlaceLead,
    copy: dict[str, Any],
    output_dir: Path,
    template_name: str,
    category_default: str,
    city_default: str,
    hero_fn,
    story_fn,
    wa_hours_msg: str,
    wa_order_fn,
) -> Path:
    import shutil
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cards = pick_reviews(lead.review_cards) or [
        ReviewCard("Cliente", "CL", 5, t[:220], "Google") for t in lead.reviews[:4]
    ]
    track = cards + cards
    display = clean_name(lead.name)
    cat = lead.category or category_default
    meta = f"{display} — {cat} en {lead.city or city_default}. {copy.get('hero_text', '')[:80]}"[:160]

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))
    env.filters["truncate_review"] = truncate_review

    html = env.get_template(template_name).render(
        name=lead.name,
        name_clean=display,
        phone=lead.phone or "Consultar",
        address=lead.address,
        short_address=short_addr(lead.address),
        street_label=street_label(lead.address),
        city=lead.city or city_default,
        category=cat,
        tagline=copy.get("tagline", f"{category_default} · {lead.city or city_default}"),
        hero_em=copy.get("hero_em", ""),
        hero_text=copy.get("hero_text", ""),
        about_title=copy.get("about_title", ""),
        about_extra=copy.get("about_extra", ""),
        features=copy.get("features", []),
        services=copy.get("services", []),
        whatsapp_intro=copy.get("whatsapp_intro", ""),
        meta_description=meta,
        rating=round(lead.rating, 1),
        stars=stars_display(lead.rating),
        review_count=lead.review_count or len(lead.reviews) * 20,
        review_cards=cards,
        carousel_reviews=track,
        hours_rows=parse_hours(lead.opening_hours),
        phone_href=phone_href(lead.phone),
        has_whatsapp=has_whatsapp(lead.phone),
        whatsapp_href=whatsapp_href(lead.phone, whatsapp_message_info(lead.name)),
        whatsapp_hours_href=whatsapp_href(lead.phone, wa_hours_msg),
        whatsapp_order_href=whatsapp_href(lead.phone, wa_order_fn(lead.name)),
        hero_image_url=hero_fn(lead.name),
        story_image_url=story_fn(lead.name),
        map_embed_url=map_embed(lead.address),
        services_count=len(copy.get("services", [])),
        review_stars=review_stars,
        year=__import__("datetime").datetime.now().year,
    )
    out = output_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    logger.info("Landing %s: %s", template_name, out)
    return out.resolve()


def render_relojeria_landing(*, lead: PlaceLead, copy: dict[str, Any], output_dir: Path) -> Path:
    return _render_salon_style(
        lead=lead,
        copy=copy,
        output_dir=output_dir,
        template_name="relojeria.html",
        category_default="Relojería",
        city_default="Barcelona",
        hero_fn=watch_hero_image,
        story_fn=watch_story_image,
        wa_hours_msg="Hola, quería pedir cita para visitar la tienda y ver relojes",
        wa_order_fn=whatsapp_message_reloj,
    )


def render_estetica_landing(*, lead: PlaceLead, copy: dict[str, Any], output_dir: Path) -> Path:
    return _render_salon_style(
        lead=lead,
        copy=copy,
        output_dir=output_dir,
        template_name="estetica.html",
        category_default="Centro de estética",
        city_default="Barcelona",
        hero_fn=estetica_hero_image,
        story_fn=estetica_story_image,
        wa_hours_msg="Hola, quería reservar una sesión de tratamiento",
        wa_order_fn=whatsapp_message_estetica,
    )
