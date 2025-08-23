import hashlib
from typing import List, Dict, Tuple
from flask import current_app
from common.cache import get_redis_client
import boto3


class AmazonTranslateService:
    def __init__(self):
        region = current_app.config.get('AWS_REGION')
        self.client = boto3.client('translate', region_name=region)
        self.redis = get_redis_client(current_app)

    @staticmethod
    def _cache_key(text: str, src: str, tgt: str, content_type: str) -> str:
        h = hashlib.sha1()
        h.update((text or '').encode('utf-8'))
        key_hash = h.hexdigest()
        return f"translate:{src}:{tgt}:{content_type}:{key_hash}"

    def translate_text(self, text: str, target_lang: str, source_lang: str = 'en', content_type: str = 'text/plain', ttl_seconds: int = 60*60*24*30) -> str:
        if not text:
            return ''
        key = self._cache_key(text, source_lang, target_lang, content_type)
        cached = self.redis.get(key)
        if cached:
            return cached.decode('utf-8')

        resp = self.client.translate_text(
            Text=text,
            SourceLanguageCode=source_lang,
            TargetLanguageCode=target_lang,
            Settings={
                'Formality': 'INFORMAL'
            },
            TerminologyNames=[],
        ) if content_type == 'text/plain' else self.client.translate_text(
            Text=text,
            SourceLanguageCode=source_lang,
            TargetLanguageCode=target_lang,
            Settings={
                'Formality': 'INFORMAL'
            },
        )

        translated = resp.get('TranslatedText', '')
        if translated:
            self.redis.setex(key, ttl_seconds, translated)
        return translated

    def translate_batch(self, items: List[Tuple[str, str]], target_lang: str, source_lang: str = 'en', content_type: str = 'text/plain') -> Dict[str, str]:
        # items is list of (id, text)
        result: Dict[str, str] = {}
        # dedupe identical texts
        unique_map: Dict[str, List[str]] = {}
        for id_, text in items:
            if not text:
                result[id_] = ''
                continue
            unique_map.setdefault(text, []).append(id_)

        # first fetch from cache
        missing_texts: List[str] = []
        cached_pairs: Dict[str, str] = {}
        for text, ids in unique_map.items():
            key = self._cache_key(text, source_lang, target_lang, content_type)
            cached = self.redis.get(key)
            if cached:
                translated = cached.decode('utf-8')
                cached_pairs[text] = translated
            else:
                missing_texts.append(text)

        # translate missing one by one
        for text in missing_texts:
            translated = self.translate_text(text, target_lang, source_lang, content_type)
            cached_pairs[text] = translated

        # map back
        for text, ids in unique_map.items():
            for id_ in ids:
                result[id_] = cached_pairs.get(text, '')
        return result
