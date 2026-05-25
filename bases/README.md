# Bases de páginas web

Modelos de landing para la automatización. Cada carpeta es una plantilla lista para generar leads.

| Carpeta | Sector | Plantilla |
|---------|--------|-----------|
| `pizzeria/` | Restaurante / pizzería | `templates/index.html` |
| `peluqueria/` | Peluquería / salón | `templates/peluqueria.html` |
| `relojeria/` | Relojería / joyería | `templates/relojeria.html` |
| `estetica/` | Centro de estética | `templates/estetica.html` |

## Ver los modelos en local

Abre `bases/index.html` en el navegador o cada `bases/{modelo}/index.html`.

Regenerar demos:

```bash
python3 generar_bases_previews.py
```

## Uso en código

```python
from templater import render_relojeria_landing, render_estetica_landing
from content_ai import generate_copy_relojeria, generate_copy_estetica
```

Modelos registrados en `templater.MODELOS_WEB`.
