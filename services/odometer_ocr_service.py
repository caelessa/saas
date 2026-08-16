import io
import re
import shutil
from dataclasses import dataclass, asdict
from typing import Optional

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


@dataclass
class OdometerOCRResult:
    suggested_km: Optional[int]
    confidence: str
    candidates: list[int]
    raw_text: str
    attempts: list[dict]
    warning: Optional[str] = None

    def to_dict(self):
        return asdict(self)


def _normalize_image(file_bytes: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(file_bytes))
    image = ImageOps.exif_transpose(image).convert('RGB')
    # Limita imagens muito grandes para não sobrecarregar o Render.
    max_side = 2200
    if max(image.size) > max_side:
        ratio = max_side / float(max(image.size))
        image = image.resize((max(1, int(image.width * ratio)), max(1, int(image.height * ratio))))
    return image


def _variants(image: Image.Image):
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)

    # Painéis normalmente têm dígitos relativamente pequenos. Ampliar ajuda o Tesseract.
    scale = 2 if max(gray.size) < 2600 else 1
    if scale > 1:
        gray = gray.resize((gray.width * scale, gray.height * scale))

    contrast = ImageEnhance.Contrast(gray).enhance(1.8)
    sharp = contrast.filter(ImageFilter.SHARPEN)
    binary = sharp.point(lambda p: 255 if p > 145 else 0)
    binary_inv = ImageOps.invert(binary)

    return [
        ('cinza_contraste', sharp),
        ('binario', binary),
        ('binario_invertido', binary_inv),
    ]


def _extract_candidates(text: str) -> list[int]:
    candidates = []
    normalized = text.upper().replace('.', '').replace(',', '').replace(' ', '')

    # Prioriza sequências numéricas compatíveis com odômetros de automóveis.
    for token in re.findall(r'(?<!\d)\d{3,7}(?!\d)', normalized):
        try:
            value = int(token)
        except ValueError:
            continue
        if 0 <= value <= 9_999_999:
            candidates.append(value)

    # Também tenta números encontrados próximos de ODO / KM no texto original.
    contextual = re.findall(r'(?:ODO(?:METER)?|KM)\D{0,12}(\d[\d\s\.,]{2,9})', text.upper())
    for token in contextual:
        digits = re.sub(r'\D', '', token)
        if 3 <= len(digits) <= 7:
            value = int(digits)
            if value not in candidates:
                candidates.insert(0, value)

    seen = set()
    unique = []
    for value in candidates:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def _score_candidate(value: int, previous_km: Optional[int], contextual: bool, frequency: int) -> float:
    score = 0.0
    if contextual:
        score += 35
    score += min(frequency, 3) * 12

    if previous_km is not None:
        if value < previous_km:
            score -= 100
        else:
            delta = value - previous_km
            if delta <= 3_000:
                score += 45
            elif delta <= 10_000:
                score += 20
            elif delta <= 50_000:
                score += 5
            else:
                score -= 20
    else:
        # Sem referência, valores típicos de odômetro recebem pequena preferência.
        if value >= 1_000:
            score += 8

    return score


def read_odometer(file_bytes: bytes, previous_km: Optional[int] = None) -> OdometerOCRResult:
    try:
        import pytesseract
    except Exception as exc:
        return OdometerOCRResult(None, 'baixa', [], '', [], f'pytesseract indisponível: {exc}')

    tesseract_path = shutil.which('tesseract')
    if not tesseract_path:
        return OdometerOCRResult(None, 'baixa', [], '', [], 'Executável Tesseract não encontrado no servidor.')
    pytesseract.pytesseract.tesseract_cmd = tesseract_path

    try:
        image = _normalize_image(file_bytes)
    except Exception as exc:
        return OdometerOCRResult(None, 'baixa', [], '', [], f'Não foi possível abrir a imagem: {exc}')

    attempts = []
    all_texts = []
    frequencies = {}
    contextual_values = set()

    configs = [
        '--oem 3 --psm 6',
        '--oem 3 --psm 11',
        '--oem 3 --psm 12',
    ]

    for variant_name, variant in _variants(image):
        for config in configs:
            try:
                text = pytesseract.image_to_string(variant, lang='eng', config=config)
            except Exception as exc:
                attempts.append({'variant': variant_name, 'config': config, 'text': '', 'error': str(exc)})
                continue

            text = (text or '').strip()
            values = _extract_candidates(text)
            upper = text.upper()
            for value in values:
                frequencies[value] = frequencies.get(value, 0) + 1
                if re.search(r'(ODO(?:METER)?|KM).{0,20}' + re.escape(str(value)), re.sub(r'[.,\s]', '', upper)):
                    contextual_values.add(value)
            attempts.append({'variant': variant_name, 'config': config, 'text': text, 'candidates': values})
            if text:
                all_texts.append(text)

    candidates = sorted(frequencies.keys(), key=lambda v: (-_score_candidate(v, previous_km, v in contextual_values, frequencies[v]), v))
    suggested = candidates[0] if candidates else None

    if suggested is None:
        confidence = 'baixa'
        warning = 'Nenhuma quilometragem confiável foi identificada. Informe o valor manualmente.'
    else:
        best_score = _score_candidate(suggested, previous_km, suggested in contextual_values, frequencies[suggested])
        if best_score >= 70:
            confidence = 'alta'
        elif best_score >= 35:
            confidence = 'média'
        else:
            confidence = 'baixa'
        warning = None
        if previous_km is not None and suggested < previous_km:
            warning = 'A leitura sugerida é menor que a quilometragem atual do veículo e deve ser conferida.'

    raw_text = '\n\n---\n\n'.join(dict.fromkeys(all_texts))
    return OdometerOCRResult(suggested, confidence, candidates[:12], raw_text[:6000], attempts, warning)
