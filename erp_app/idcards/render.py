import io
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    import qrcode
except Exception:
    qrcode = None


def _find_font(font_candidates):
    for cand in font_candidates:
        try:
            p = Path(cand)
            if p.exists():
                return str(p)
        except Exception:
            continue
    return None


def _load_fonts():
    base_font_dir = Path(__file__).resolve().parent.parent / 'static' / 'erp_app' / 'fonts'
    static_font_dir = Path(__file__).resolve().parent.parent / 'static' / 'erp_app' / 'fonts'
    # Also check common locations
    fonts = {}
    # Montserrat
    for name in ['Montserrat-Bold.ttf', 'Montserrat-ExtraBold.ttf', 'Montserrat-SemiBold.ttf']:
        p = base_font_dir / name
        if p.exists():
            fonts['heading_bold'] = str(p)
            break
    if 'heading_bold' not in fonts:
        for name in ['Inter-Bold.ttf', 'DejaVuSans-Bold.ttf']:
            p = base_font_dir / name
            if not p.exists():
                # try system
                pass
            else:
                fonts['heading_bold'] = str(p)
                break
    # Inter
    for name in ['Inter-Regular.ttf', 'Inter-Medium.ttf']:
        p = base_font_dir / name
        if p.exists():
            fonts['body'] = str(p)
            break
    if 'body' not in fonts:
        fonts['body'] = fonts.get('heading_bold')
    # Noto Sans Devanagari
    for name in ['NotoSansDevanagari-Regular.ttf', 'NotoSansDevanagari-Bold.ttf']:
        p = base_font_dir / name
        if p.exists():
            fonts['devanagari'] = str(p)
            break
    return fonts


def _rounded_rectangle_mask(size, radius):
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def _get_font(path, size):
    if path and Path(path).exists():
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            pass
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def render_id_card_png(data, render_scale=2, output_size=(650, 1030)):
    """Render ID card as PNG bytes."""
    fonts = _load_fonts()
    w, h = output_size[0] * render_scale, output_size[1] * render_scale
    card = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    radius = int(40 * render_scale)
    bg_mask = _rounded_rectangle_mask((w, h), radius)
    white_bg = Image.new('RGBA', (w, h), (255, 255, 255, 255))
    card = Image.composite(white_bg, card, bg_mask)
    draw = ImageDraw.Draw(card)
    header_h = int(65 * render_scale)
    header_mask = _rounded_rectangle_mask((w, header_h), radius)
    header = Image.new('RGBA', (w, header_h), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(header)
    for i in range(header_h):
        t = i / header_h if header_h else 0
        r = int(59 + (124 - 59) * t)
        g = int(91 + (77 - 91) * t)
        b = int(255 + (235 - 255) * t)
        hdraw.rectangle((0, i, w, i + 1), fill=(r, g, b, 255))
    header = Image.composite(header, Image.new('RGBA', (w, header_h), (0, 0, 0, 0)), header_mask)
    card.alpha_composite(header, (0, 0))
    draw = ImageDraw.Draw(card)
    logo_path = Path(__file__).resolve().parent.parent / 'static' / 'erp_app' / 'images' / 'AURALITH_logo.png'
    if logo_path.exists():
        try:
            logo = Image.open(logo_path).convert('RGBA')
            logo_h = int(38 * render_scale)
            ratio = logo_h / logo.height
            logo_w = int(logo.width * ratio)
            logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
            card.alpha_composite(logo, (int(40 * render_scale), int((header_h - logo_h) // 2)))
        except Exception:
            pass
    try:
        draw.text((int(95 * render_scale), int(18 * render_scale)), 'AURALITH BIT', fill=(45, 91, 219, 255), font=_get_font(fonts.get('heading_bold'), int(22 * render_scale)))
        draw.text((int(95 * render_scale), int(42 * render_scale)), 'DESIGN. DEVELOP. DELIVER.', fill=(45, 181, 168, 255), font=_get_font(fonts.get('body'), int(12 * render_scale)))
    except Exception:
        pass
    pill_y = int(95 * render_scale)
    pill_w = int(200 * render_scale)
    pill_h = int(32 * render_scale)
    pill_x = (w - pill_w) // 2
    pill = Image.new('RGBA', (pill_w, pill_h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pill)
    pd.rounded_rectangle((0, 0, pill_w, pill_h), radius=int(16 * render_scale), fill=(245, 247, 250, 255), outline=(220, 225, 235, 255), width=2)
    card.alpha_composite(pill, (pill_x, pill_y))
    draw = ImageDraw.Draw(card)
    try:
        draw.text((w // 2, pill_y + pill_h // 2), f"ID : {data.get('code', '')}", fill=(30, 60, 120, 255), font=_get_font(fonts.get('body'), int(14 * render_scale)), anchor='mm')
    except Exception:
        pass
    photo_cy = int(230 * render_scale)
    photo_r = int(105 * render_scale)
    photo_cx = w // 2
    ring = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    rd = ImageDraw.Draw(ring)
    rd.ellipse((photo_cx - photo_r - int(6*render_scale), photo_cy - photo_r - int(6*render_scale), photo_cx + photo_r + int(6*render_scale), photo_cy + photo_r + int(6*render_scale)), outline=(53, 189, 178, 255), width=int(6*render_scale))
    card.alpha_composite(ring)
    draw = ImageDraw.Draw(card)
    photo = data.get('photo')
    if photo is not None:
        try:
            if isinstance(photo, (str, Path)):
                pimg = Image.open(photo).convert('RGBA')
            elif hasattr(photo, 'read'):
                pimg = Image.open(photo).convert('RGBA')
            else:
                pimg = photo.convert('RGBA')
            size = min(pimg.size)
            left = (pimg.width - size) // 2
            top = (pimg.height - size) // 2
            pimg = pimg.crop((left, top, left + size, top + size))
            pimg = pimg.resize((photo_r * 2, photo_r * 2), Image.LANCZOS)
            mask = Image.new('L', pimg.size, 0)
            md = ImageDraw.Draw(mask)
            md.ellipse((0, 0, pimg.size[0], pimg.size[1]), fill=255)
            out = Image.new('RGBA', pimg.size, (0, 0, 0, 0))
            out.paste(pimg, (0, 0), mask)
            card.alpha_composite(out, (photo_cx - photo_r, photo_cy - photo_r))
        except Exception:
            try:
                draw.ellipse((photo_cx - photo_r, photo_cy - photo_r, photo_cx + photo_r, photo_cy + photo_r), fill=(230, 240, 255, 255))
                name = data.get('name', '') or '?'
                draw.text((photo_cx, photo_cy), name[:1].upper(), fill=(40, 80, 150, 255), font=_get_font(fonts.get('heading_bold'), int(80*render_scale)), anchor='mm')
            except Exception:
                pass
    else:
        try:
            draw.ellipse((photo_cx - photo_r, photo_cy - photo_r, photo_cx + photo_r, photo_cy + photo_r), fill=(230, 240, 255, 255))
            name = data.get('name', '') or '?'
            draw.text((photo_cx, photo_cy), name[:1].upper(), fill=(40, 80, 150, 255), font=_get_font(fonts.get('heading_bold'), int(80*render_scale)), anchor='mm')
        except Exception:
            pass
    try:
        draw.text((w // 2, int(380 * render_scale)), (data.get('name', '') or '').upper(), fill=(45, 91, 219, 255), font=_get_font(fonts.get('heading_bold'), int(38*render_scale)), anchor='mm')
    except Exception:
        pass
    try:
        designation = data.get('designation') or data.get('role') or data.get('course') or '-'
        draw.text((w // 2, int(420 * render_scale)), str(designation).upper(), fill=(40, 60, 90, 255), font=_get_font(fonts.get('body'), int(16*render_scale)), anchor='mm')
    except Exception:
        pass
    draw.line((int(60*render_scale), int(450*render_scale), int((w/2 - 10)*render_scale), int(450*render_scale)), fill=(200, 210, 230, 255), width=2)
    draw.line((int((w/2 + 10)*render_scale), int(450*render_scale), int(w - 60*render_scale), int(450*render_scale)), fill=(200, 210, 230, 255), width=2)
    col_y = int(480 * render_scale)
    try:
        draw.text((int(80*render_scale), col_y), 'DEPARTMENT', fill=(120, 130, 150, 255), font=_get_font(fonts.get('body'), int(12*render_scale)))
        dept = data.get('department') or data.get('course') or '-'
        draw.text((int(80*render_scale), col_y + int(24*render_scale)), str(dept), fill=(30, 60, 120, 255), font=_get_font(fonts.get('heading_bold'), int(16*render_scale)))
    except Exception:
        pass
    draw.line((w//2, int(470*render_scale), w//2, int(520*render_scale)), fill=(200, 210, 230, 255), width=2)
    try:
        draw.text((int(w//2 + 30*render_scale), col_y), 'CONTACT', fill=(120, 130, 150, 255), font=_get_font(fonts.get('body'), int(12*render_scale)))
        contact = data.get('contact') or data.get('phone') or '-'
        draw.text((int(w//2 + 30*render_scale), col_y + int(24*render_scale)), str(contact), fill=(30, 60, 120, 255), font=_get_font(fonts.get('heading_bold'), int(16*render_scale)))
    except Exception:
        pass
    qr_x = int(450 * render_scale)
    qr_y = int(560 * render_scale)
    qr_size = int(150 * render_scale)
    qframe = Image.new('RGBA', (qr_size + int(30*render_scale), qr_size + int(30*render_scale)), (0,0,0,0))
    qfd = ImageDraw.Draw(qframe)
    qfd.rounded_rectangle((int(4*render_scale), int(4*render_scale), qr_size + int(26*render_scale), qr_size + int(26*render_scale)), radius=int(16*render_scale), fill=(0,0,0,30))
    qfd.rounded_rectangle((0,0, qr_size + int(22*render_scale), qr_size + int(22*render_scale)), radius=int(16*render_scale), fill=(255,255,255,255), outline=(53,189,178,255), width=int(4*render_scale))
    card.alpha_composite(qframe, (qr_x - int(10*render_scale), qr_y - int(10*render_scale)))
    if qrcode is not None:
        try:
            qr_url = data.get('qr_url') or ''
            qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=6, border=2)
            qr.add_data(qr_url)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="#1A4B8D", back_color="white").convert('RGBA')
            qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)
            card.alpha_composite(qr_img, (qr_x + int(6*render_scale), qr_y + int(6*render_scale)))
        except Exception:
            pass
    try:
        for i in range(3):
            for j in range(3):
                x = int(320 * render_scale) + i * int(10*render_scale)
                y = int(580 * render_scale) + j * int(10*render_scale)
                draw.ellipse((x,y,x+int(6*render_scale),y+int(6*render_scale)), fill=(53,189,178,255))
        for i in range(3):
            for j in range(3):
                x = int(550 * render_scale) + i * int(10*render_scale)
                y = int(580 * render_scale) + j * int(10*render_scale)
                draw.ellipse((x,y,x+int(6*render_scale),y+int(6*render_scale)), fill=(53,189,178,255))
    except Exception:
        pass
    footer_h = int(50 * render_scale)
    footer = Image.new('RGBA', (w, footer_h), (0,0,0,0))
    fdraw = ImageDraw.Draw(footer)
    for i in range(footer_h):
        t = i / footer_h if footer_h else 0
        r = int(59 + (124 - 59) * t)
        g = int(91 + (77 - 91) * t)
        b = int(255 + (235 - 255) * t)
        fdraw.rectangle((0, i, w, i + 1), fill=(r, g, b, 255))
    footer_mask = _rounded_rectangle_mask((w, footer_h), radius)
    footer = Image.composite(footer, Image.new('RGBA', (w, footer_h), (0,0,0,0)), footer_mask)
    card.alpha_composite(footer, (0, h - footer_h))
    draw = ImageDraw.Draw(card)
    try:
        draw.text((w // 2, h - footer_h // 2), 'AURALITH BIT | BHAIRAHAWA, SNP-08 | 9766715783', fill=(243, 247, 255, 255), font=_get_font(fonts.get('body'), int(14*render_scale)), anchor='mm')
    except Exception:
        pass
    try:
        strip_h = int(30 * render_scale)
        strip = Image.new('RGBA', (w, strip_h), (250, 252, 255, 255))
        card.alpha_composite(strip, (0, h - footer_h - strip_h))
        draw = ImageDraw.Draw(card)
        gcx = int(200 * render_scale)
        gcy = h - footer_h - strip_h // 2
        gr = int(10 * render_scale)
        draw.ellipse((gcx - gr, gcy - gr, gcx + gr, gcy + gr), outline=(40, 80, 150, 255), width=2)
        draw.line((gcx, gcy - gr, gcx, gcy + gr), fill=(40, 80, 150, 255), width=2)
        draw.arc((gcx - gr, gcy - int(gr//2), gcx + gr, gcy + int(gr//2)), 0, 360, fill=(40, 80, 150, 255), width=1)
        draw.text((gcx + int(18*render_scale), gcy), 'www.auralithbit.com.np', fill=(40, 80, 150, 255), font=_get_font(fonts.get('body'), int(12*render_scale)), anchor='lm')
    except Exception:
        pass
    card_out = card.resize(output_size, Image.LANCZOS)
    out = io.BytesIO()
    card_out.save(out, format='PNG')
    return out.getvalue()


def render_id_card_pdf(png_bytes, output_path=None):
    try:
        img = Image.open(io.BytesIO(png_bytes))
        if output_path:
            img.save(output_path, 'PDF')
            return output_path
        out = io.BytesIO()
        img.save(out, 'PDF')
        return out.getvalue()
    except Exception:
        out = io.BytesIO()
        return out.getvalue()
