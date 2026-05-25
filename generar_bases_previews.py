"""
Genera las bases de demostración en bases/{modelo}/index.html
para previsualizar cada plantilla sin APIs externas.
"""

from __future__ import annotations

import logging
from pathlib import Path

from scraper import PlaceLead, ReviewCard
from templater import (
    MODELOS_WEB,
    render_estetica_landing,
    render_peluqueria_landing,
    render_relojeria_landing,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
BASES_DIR = ROOT / "bases"

DEMO_COPY = {
    "relojeria": {
        "tagline": "Relojería · Barcelona · Tradición",
        "hero_em": "El tiempo, en buenas manos",
        "hero_text": "Relojes seleccionados, revisiones y asesoramiento experto en un espacio elegante pensado para ti.",
        "about_title": "precisión y confianza",
        "about_extra": "Más de una década cuidando cada detalle de tu reloj.",
        "features": [
            {"emoji": "⌚", "title": "Colección premium", "text": "Marcas reconocidas y piezas exclusivas."},
            {"emoji": "🔧", "title": "Taller propio", "text": "Revisiones, pilas y ajustes con garantía."},
            {"emoji": "✨", "title": "Asesor personal", "text": "Te guiamos para acertar con tu reloj ideal."},
        ],
        "services": ["Relojes de pulsera", "Relojes de pared", "Revisiones", "Joyas", "Compra y venta"],
        "whatsapp_intro": "Consulta disponibilidad o pide cita en tienda por WhatsApp.",
    },
    "estetica": {
        "tagline": "Estética · Barcelona · Bienestar",
        "hero_em": "Tu ritual de belleza",
        "hero_text": "Tratamientos faciales y corporales en un ambiente sereno, con profesionales que te escuchan.",
        "about_title": "cuidado integral",
        "about_extra": "Tecnología y tacto humano en cada sesión.",
        "features": [
            {"emoji": "✨", "title": "Facial avanzado", "text": "Protocolos para luminosidad y firmeza."},
            {"emoji": "💆", "title": "Cuerpo y relax", "text": "Masajes y tratamientos descontracturantes."},
            {"emoji": "🌿", "title": "Plan personal", "text": "Rutinas adaptadas a tu piel y ritmo."},
        ],
        "services": ["Facial", "Corporal", "Depilación láser", "Manicura", "Masajes", "Peeling"],
        "whatsapp_intro": "Reserva tu cita por WhatsApp en menos de un minuto.",
    },
    "peluqueria": {
        "tagline": "Peluquería · Sitges · Estilo",
        "hero_em": "Tu mejor versión empieza aquí",
        "hero_text": "Corte, color y tratamientos en un salón acogedor con profesionales apasionados.",
        "about_title": "tu estilo",
        "about_extra": "Productos de calidad y un trato que marca la diferencia.",
        "features": [
            {"emoji": "✂️", "title": "Corte y color", "text": "Tendencias y clásicos con acabado impecable."},
            {"emoji": "💇", "title": "Tratamientos", "text": "Hidratación, brillo y cuidado del cuero cabelludo."},
            {"emoji": "✨", "title": "Eventos", "text": "Peinados para bodas, graduaciones y más."},
        ],
        "services": ["Corte mujer", "Coloración", "Peinado", "Barbería", "Tratamientos"],
        "whatsapp_intro": "Reserva tu cita por WhatsApp.",
    },
}

DEMO_LEADS = {
    "relojeria": PlaceLead(
        place_id="demo-reloj",
        name="Relojería Aurora",
        address="Carrer de Balmes, 120, 08008 Barcelona, España",
        phone="932 11 22 33",
        city="Barcelona",
        category="Relojería",
        rating=4.8,
        review_count=124,
        opening_hours=["Lunes: 10:00 – 20:00", "Martes: 10:00 – 20:00", "Sábado: 10:30 – 14:00"],
        reviews=["Excelente atención y gran variedad de relojes.", "Me cambiaron la pila al momento."],
        review_cards=[
            ReviewCard("María G.", "MG", 5, "Profesionales y trato muy cercano. Repetiré sin duda.", "Google"),
            ReviewCard("Joan P.", "JP", 5, "Compré mi primer reloj suizo aquí. Asesoramiento top.", "Google"),
        ],
    ),
    "estetica": PlaceLead(
        place_id="demo-estetica",
        name="Centro Estética Luna",
        address="Passeig de Gràcia, 45, 08007 Barcelona, España",
        phone="934 55 66 77",
        city="Barcelona",
        category="Centro de estética",
        rating=4.9,
        review_count=210,
        opening_hours=["Lunes: 9:30 – 20:00", "Miércoles: 9:30 – 20:00", "Domingo: Cerrado"],
        reviews=["Ambiente increíble y resultados visibles.", "La mejor depilación que he probado."],
        review_cards=[
            ReviewCard("Laura S.", "LS", 5, "Salí renovada. Trato delicado y sin presión.", "Google"),
            ReviewCard("Elena R.", "ER", 5, "Faciales personalizados. Mi piel nunca estuvo mejor.", "Google"),
        ],
    ),
    "peluqueria": PlaceLead(
        place_id="demo-pelu",
        name="Salón Belleza Nova",
        address="Carrer Major, 10, 08870 Sitges, Barcelona, España",
        phone="938 12 34 56",
        city="Sitges",
        category="Peluquería",
        rating=4.7,
        review_count=89,
        opening_hours=["Martes: 10:00 – 19:00", "Viernes: 10:00 – 20:00"],
        reviews=["Me encantó el color y el trato.", "Sitio acogedor y muy profesional."],
        review_cards=[
            ReviewCard("Ana M.", "AM", 5, "El mejor corte que me han hecho en años.", "Google"),
        ],
    ),
}

RENDERERS = {
    "relojeria": render_relojeria_landing,
    "estetica": render_estetica_landing,
    "peluqueria": render_peluqueria_landing,
}


def main() -> None:
    BASES_DIR.mkdir(parents=True, exist_ok=True)
    for modelo, info in MODELOS_WEB.items():
        if modelo not in RENDERERS:
            log.info("Omitido (sin renderer demo): %s", modelo)
            continue
        out = BASES_DIR / modelo
        lead = DEMO_LEADS[modelo]
        copy = DEMO_COPY[modelo]
        path = RENDERERS[modelo](lead=lead, copy=copy, output_dir=out)
        log.info("✓ bases/%s/index.html — %s", modelo, info["categoria"])

    # Índice de modelos
    index_lines = [
        "<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>Bases de páginas web</title>",
        "<style>body{font-family:system-ui;max-width:640px;margin:3rem auto;padding:0 1.5rem}",
        "a{display:block;padding:1rem;margin:.5rem 0;border:1px solid #ddd;border-radius:12px;text-decoration:none;color:#111}",
        "a:hover{border-color:#888}h1{font-size:1.5rem}</style></head><body>",
        "<h1>Bases de páginas web</h1><p>Modelos disponibles para automatización:</p>",
    ]
    for modelo, info in MODELOS_WEB.items():
        if (BASES_DIR / modelo / "index.html").is_file():
            index_lines.append(
                f"<a href='{modelo}/index.html'><strong>{info['categoria']}</strong> "
                f"<small>({modelo})</small></a>"
            )
    index_lines.append("</body></html>")
    (BASES_DIR / "index.html").write_text("\n".join(index_lines), encoding="utf-8")
    log.info("✓ bases/index.html — índice de modelos")


if __name__ == "__main__":
    main()
