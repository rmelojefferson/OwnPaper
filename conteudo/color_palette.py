import colorsys
from typing import Dict, Tuple

try:
    from coloraide import Color
except Exception:  # pragma: no cover - fallback quando dependência ainda não está instalada
    Color = None


def _normalize_hex(value: str, fallback: str) -> str:
    texto = (value or "").strip()
    if len(texto) == 7 and texto.startswith("#"):
        try:
            int(texto[1:], 16)
            return texto.lower()
        except ValueError:
            pass
    return fallback.lower()


def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
    cor = _normalize_hex(value, "#000000")
    return int(cor[1:3], 16), int(cor[3:5], 16), int(cor[5:7], 16)


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    rr = max(0, min(255, round(r)))
    gg = max(0, min(255, round(g)))
    bb = max(0, min(255, round(b)))
    return f"#{rr:02x}{gg:02x}{bb:02x}"


def _clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(max_value, value))


def _hex_to_hls(value: str) -> Tuple[float, float, float]:
    r, g, b = _hex_to_rgb(value)
    return colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)


def _hls_to_hex(h: float, l: float, s: float) -> str:
    rr, gg, bb = colorsys.hls_to_rgb(h % 1.0, _clamp(l), _clamp(s))
    return _rgb_to_hex(rr * 255.0, gg * 255.0, bb * 255.0)


def _mix(a: str, b: str, weight_a: float) -> str:
    ar, ag, ab = _hex_to_rgb(a)
    br, bg, bb = _hex_to_rgb(b)
    wa = max(0.0, min(1.0, weight_a))
    wb = 1.0 - wa
    return _rgb_to_hex((ar * wa) + (br * wb), (ag * wa) + (bg * wb), (ab * wa) + (bb * wb))


def _oklch_to_hex(l: float, c: float, h: float) -> str:
    if Color is None:
        return "#000000"
    tone = Color("oklch", [_clamp(l), max(0.0, c), (h or 0.0) % 360.0]).convert("srgb").fit(method="clip")
    return tone.to_string(hex=True).lower()


def _hex_to_oklch(value: str) -> Tuple[float, float, float]:
    if Color is None:
        return 0.5, 0.0, 240.0
    color = Color(_normalize_hex(value, "#000000")).convert("oklch")
    l, c, h = color.coords()
    return float(l), float(c), float(0.0 if h is None else h)


def _srgb_channel(value: int) -> float:
    c = value / 255.0
    if c <= 0.03928:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _luminance(color: str) -> float:
    r, g, b = _hex_to_rgb(color)
    return (
        0.2126 * _srgb_channel(r)
        + 0.7152 * _srgb_channel(g)
        + 0.0722 * _srgb_channel(b)
    )


def _contrast_ratio(fg: str, bg: str) -> float:
    l1 = _luminance(fg)
    l2 = _luminance(bg)
    claro = max(l1, l2)
    escuro = min(l1, l2)
    return (claro + 0.05) / (escuro + 0.05)


def _ensure_contrast(fg: str, bg: str, min_ratio: float = 4.5) -> str:
    base = _normalize_hex(fg, "#000000")
    if _contrast_ratio(base, bg) >= min_ratio:
        return base

    melhor = base
    melhor_contraste = _contrast_ratio(base, bg)
    alvo = "#000000" if _luminance(bg) > 0.45 else "#ffffff"
    for i in range(1, 21):
        candidato = _mix(alvo, base, i / 20.0)
        contraste = _contrast_ratio(candidato, bg)
        if contraste > melhor_contraste:
            melhor = candidato
            melhor_contraste = contraste
        if contraste >= min_ratio:
            return candidato
    return melhor


def _ensure_contrast_oklch(fg: str, bg: str, min_ratio: float = 4.5) -> str:
    base = _normalize_hex(fg, "#000000")
    if _contrast_ratio(base, bg) >= min_ratio:
        return base

    if Color is None:
        return _ensure_contrast(base, bg, min_ratio=min_ratio)

    l, c, h = _hex_to_oklch(base)
    bg_luma = _luminance(bg)
    step = -0.03 if bg_luma > 0.5 else 0.03
    melhor = base
    melhor_contraste = _contrast_ratio(base, bg)
    atual_l = l

    for _ in range(24):
        atual_l = _clamp(atual_l + step)
        candidato = _oklch_to_hex(atual_l, c, h)
        contraste = _contrast_ratio(candidato, bg)
        if contraste > melhor_contraste:
            melhor = candidato
            melhor_contraste = contraste
        if contraste >= min_ratio:
            return candidato
        if atual_l <= 0.0 or atual_l >= 1.0:
            break
    return melhor


RATIO_AA_NORMAL = 4.5
RATIO_AAA_NORMAL = 7.0


def _best_text_for_bg(bg: str, min_ratio: float = RATIO_AA_NORMAL) -> str:
    preto = "#000000"
    branco = "#ffffff"
    r_preto = _contrast_ratio(preto, bg)
    r_branco = _contrast_ratio(branco, bg)
    escolhido = preto if r_preto >= r_branco else branco
    if max(r_preto, r_branco) >= min_ratio:
        return escolhido
    return _ensure_contrast(escolhido, bg, min_ratio=min_ratio)


def suggest_secondary(base_primary: str) -> str:
    if Color is not None:
        l, c, h = _hex_to_oklch(base_primary)
        nh = (h + 38.0) % 360.0
        nl = 0.62 if l < 0.55 else 0.52
        nc = min(max(c + 0.06, 0.14), 0.28)
        return _oklch_to_hex(nl, nc, nh)

    prim = _normalize_hex(base_primary, "#0f172a")
    h, l, s = _hex_to_hls(prim)
    # Análogo deslocado para preservar harmonia e evitar contraste "sujo".
    h = (h + (38.0 / 360.0)) % 1.0
    s = _clamp(max(0.62, s + 0.12), 0.62, 0.9)
    l = 0.48 if l > 0.58 else 0.56
    return _hls_to_hex(h, l, s)


def _tone(color: str, *, l: float = None, s_scale: float = 1.0, s_min: float = 0.0) -> str:
    h, old_l, old_s = _hex_to_hls(color)
    new_l = old_l if l is None else l
    new_s = _clamp(max(s_min, old_s * s_scale))
    return _hls_to_hex(h, new_l, new_s)


def derive_palette(base_primary: str, base_secondary: str) -> Dict[str, str]:
    c1 = _normalize_hex(base_primary, "#0f172a")
    c2_raw = _normalize_hex(base_secondary, "#1d4ed8")
    c2 = c2_raw if c2_raw != "#1d4ed8" else suggest_secondary(c1)

    if Color is not None:
        _, p_c, p_h = _hex_to_oklch(c1)
        _, s_c, s_h = _hex_to_oklch(c2)

        accent = _oklch_to_hex(0.58, min(max(s_c, 0.14), 0.30), s_h)

        light_bg = _oklch_to_hex(0.985, min(0.02, p_c * 0.16), p_h)
        light_surface = _oklch_to_hex(0.995, min(0.014, p_c * 0.1), p_h)
        light_muted_base = _oklch_to_hex(0.40, min(0.05, p_c * 0.35 + 0.01), p_h)
        light_border = _oklch_to_hex(0.86, min(0.045, p_c * 0.42 + 0.008), p_h)
        light_link = _ensure_contrast_oklch(
            _oklch_to_hex(0.36, min(max(s_c, 0.12), 0.24), s_h),
            light_bg,
            RATIO_AAA_NORMAL,
        )
        light_accent = _ensure_contrast_oklch(
            _oklch_to_hex(0.50, min(max(s_c, 0.14), 0.30), s_h),
            light_bg,
            RATIO_AA_NORMAL,
        )
        light_muted = _ensure_contrast_oklch(light_muted_base, light_bg, RATIO_AA_NORMAL)

        dark_bg = _oklch_to_hex(0.17, min(0.05, p_c * 0.38 + 0.01), p_h)
        dark_surface = _oklch_to_hex(0.22, min(0.06, p_c * 0.42 + 0.012), p_h)
        dark_muted_base = _oklch_to_hex(0.80, min(0.045, p_c * 0.24 + 0.008), p_h)
        dark_border = _oklch_to_hex(0.34, min(0.055, p_c * 0.45 + 0.012), p_h)
        dark_link = _ensure_contrast_oklch(
            _oklch_to_hex(0.79, min(max(s_c * 0.7, 0.10), 0.20), s_h),
            dark_bg,
            RATIO_AAA_NORMAL,
        )
        dark_accent = _ensure_contrast_oklch(
            _oklch_to_hex(0.72, min(max(s_c * 0.75, 0.12), 0.24), s_h),
            dark_bg,
            RATIO_AA_NORMAL,
        )
        dark_muted = _ensure_contrast_oklch(dark_muted_base, dark_bg, RATIO_AA_NORMAL)
        surface_tint = _oklch_to_hex(0.93, min(0.05, s_c * 0.22 + 0.01), s_h)
    else:
        # Fallback sem biblioteca externa.
        accent = _tone(c2, l=0.48, s_scale=1.05, s_min=0.64)

        light_bg = _tone(c1, l=0.985, s_scale=0.12)
        light_surface = _tone(c1, l=0.995, s_scale=0.08)
        light_muted = _tone(c1, l=0.33, s_scale=0.22, s_min=0.1)
        light_border = _tone(c1, l=0.84, s_scale=0.22)
        light_link = _ensure_contrast(_tone(c1, l=0.28, s_scale=0.72, s_min=0.35), light_bg, RATIO_AAA_NORMAL)
        light_accent = _ensure_contrast(_tone(c2, l=0.36, s_scale=0.95, s_min=0.5), light_bg, RATIO_AA_NORMAL)
        light_muted = _ensure_contrast(light_muted, light_bg, RATIO_AA_NORMAL)

        dark_bg = _tone(c1, l=0.09, s_scale=0.55, s_min=0.22)
        dark_surface = _tone(c1, l=0.14, s_scale=0.5, s_min=0.2)
        dark_muted = _tone(c1, l=0.74, s_scale=0.25, s_min=0.08)
        dark_border = _tone(c1, l=0.27, s_scale=0.32, s_min=0.12)
        dark_link = _ensure_contrast(_tone(c1, l=0.78, s_scale=0.62, s_min=0.35), dark_bg, RATIO_AAA_NORMAL)
        dark_accent = _ensure_contrast(_tone(c2, l=0.72, s_scale=0.78, s_min=0.3), dark_bg, RATIO_AA_NORMAL)
        dark_muted = _ensure_contrast(dark_muted, dark_bg, RATIO_AA_NORMAL)
        surface_tint = _tone(c2, l=0.93, s_scale=0.22)

    light_button_bg = light_surface
    light_button_text = _ensure_contrast(light_text := "#000000", light_button_bg, RATIO_AA_NORMAL)
    light_button_hover_bg = _ensure_contrast(light_accent, light_bg, RATIO_AA_NORMAL)
    light_button_hover_text = _best_text_for_bg(light_button_hover_bg, RATIO_AA_NORMAL)
    light_button_disabled_bg = _mix(light_surface, light_muted, 0.82)
    light_button_disabled_text = _ensure_contrast(light_muted, light_button_disabled_bg, 3.0)

    dark_button_bg = dark_surface
    dark_button_text = _ensure_contrast(dark_text := "#ffffff", dark_button_bg, RATIO_AA_NORMAL)
    dark_button_hover_bg = _ensure_contrast(dark_accent, dark_bg, RATIO_AA_NORMAL)
    dark_button_hover_text = _best_text_for_bg(dark_button_hover_bg, RATIO_AA_NORMAL)
    dark_button_disabled_bg = _mix(dark_surface, dark_muted, 0.84)
    dark_button_disabled_text = _ensure_contrast(dark_muted, dark_button_disabled_bg, 3.0)

    return {
        "base_1": c1,
        "base_2": c2,
        "accent": accent,
        "surface_tint": surface_tint,
        "light_bg": light_bg,
        "light_surface": light_surface,
        "light_text": "#000000",
        "light_muted": light_muted,
        "light_border": light_border,
        "light_link": light_link,
        "light_accent": light_accent,
        "dark_bg": dark_bg,
        "dark_surface": dark_surface,
        "dark_text": "#ffffff",
        "dark_muted": dark_muted,
        "dark_border": dark_border,
        "dark_link": dark_link,
        "dark_accent": dark_accent,
        "light_button_bg": light_button_bg,
        "light_button_text": light_button_text,
        "light_button_hover_bg": light_button_hover_bg,
        "light_button_hover_text": light_button_hover_text,
        "light_button_disabled_bg": light_button_disabled_bg,
        "light_button_disabled_text": light_button_disabled_text,
        "dark_button_bg": dark_button_bg,
        "dark_button_text": dark_button_text,
        "dark_button_hover_bg": dark_button_hover_bg,
        "dark_button_hover_text": dark_button_hover_text,
        "dark_button_disabled_bg": dark_button_disabled_bg,
        "dark_button_disabled_text": dark_button_disabled_text,
    }
