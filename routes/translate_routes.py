from flask import Blueprint, request, jsonify, current_app
from services.translate_service import AmazonTranslateService

translate_bp = Blueprint('translate', __name__)


@translate_bp.route('/api/translate', methods=['POST'])
def translate_single():
    if not current_app.config.get('FEATURE_TRANSLATION'):
        return jsonify({'error': 'Translation feature disabled'}), 404
    data = request.get_json(silent=True) or {}
    text = data.get('text', '')
    target = data.get('targetLang')
    source = data.get('sourceLang', 'en')
    content_type = data.get('contentType', 'text/plain')
    if not text or not target:
        return jsonify({'error': 'text and targetLang are required'}), 400
    svc = AmazonTranslateService()
    translated = svc.translate_text(text, target, source, content_type)
    return jsonify({'translatedText': translated})


@translate_bp.route('/api/translate/batch', methods=['POST'])
def translate_batch():
    if not current_app.config.get('FEATURE_TRANSLATION'):
        return jsonify({'error': 'Translation feature disabled'}), 404
    data = request.get_json(silent=True) or {}
    items = data.get('items', [])
    target = data.get('targetLang')
    source = data.get('sourceLang', 'en')
    content_type = data.get('contentType', 'text/plain')
    if not isinstance(items, list) or not target:
        return jsonify({'error': 'items (list) and targetLang are required'}), 400
    pairs = []
    for it in items:
        if isinstance(it, dict) and 'id' in it and 'text' in it:
            pairs.append((str(it['id']), str(it['text'])))
    svc = AmazonTranslateService()
    result = svc.translate_batch(pairs, target, source, content_type)
    return jsonify({'items': [{'id': id_, 'translatedText': txt} for id_, txt in result.items()]})
