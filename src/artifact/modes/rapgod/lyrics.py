"""Lyrics generator for RapGod mode.

Uses Gemini 3.0 Flash to generate Russian rap lyrics
based on selected words, genre, AND the person's photo.

The AI analyzes the photo and incorporates fun observations
about the person's appearance into the lyrics.
"""

import logging
import json
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from artifact.ai.client import get_gemini_client, GeminiModel
from artifact.modes.rapgod.wordbank import WordSelection, GENRES

logger = logging.getLogger(__name__)


@dataclass
class GeneratedLyrics:
    """Generated lyrics with metadata."""

    title: str
    artist: str
    genre: str
    bpm: int
    mood: str
    hook: str
    verse1: str
    verse2: Optional[str]
    tags: List[str]
    one_liner: str  # Short tagline for receipt
    raw_response: str


# System prompt for the rap lyricist AI
RAP_LYRICIST_SYSTEM_PROMPT = """Ты легендарный гострайтер русского рэпа. Твоя задача — писать ОГНЕННЫЕ треки для клубной аудитории.

=== ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ ===
Символы: А-Яа-я A-Za-z 0-9 . , ! ? : ( ) / % *
НЕЛЬЗЯ: эмодзи, кавычки особые, многоточие, любые другие символы!
Язык: ТОЛЬКО РУССКИЙ (можно английские слова как сленг)

=== СТИЛЬ ===
- Клубный вайб, остроумный, дерзкий но не токсичный
- Можно лёгкий мат (блять, хуй, пиздец) но без агрессии
- Рифмы должны быть СВЕЖИМИ, не банальными
- Внутренние рифмы, панчи, флоу
- НЕ имитируй конкретных артистов, создавай свой стиль

=== ПЕРСОНАЛИЗАЦИЯ ПО ФОТО ===
Если есть фото человека:
- Посмотри на внешность: одежду, стиль, прическу, выражение лица, вайб
- Вплети 2-3 ЗАБАВНЫХ наблюдения о внешности в текст
- Это должно быть КОМПЛИМЕНТАРНО и СМЕШНО, не обидно
- НЕ описывай внешность напрямую - обыграй её креативно через рифмы и панчи!

=== СТРУКТУРА ===
Всегда возвращай ТОЛЬКО валидный JSON без markdown:
{
  "title": "Название трека (креативное, запоминающееся)",
  "artist": "ARTIFACT AI",
  "genre": "trap|drill|cloud|boombap|phonk",
  "bpm": 140,
  "mood": "агрессивно|клубно|меланхолично|дерзко|романтично",
  "lyrics": {
    "hook": "Припев 4-6 строк. Цепляющий, можно повторы. Переносы через \\n",
    "verse1": "Куплет 8-12 строк. Раскрой тему. Переносы через \\n",
    "verse2": "Второй куплет 8-12 строк (опционально). Переносы через \\n"
  },
  "tags": ["тег1", "тег2", "тег3"],
  "one_liner": "Короткая фраза для чека (до 30 символов)"
}

=== ВАЖНО ===
- ВСЕ выбранные слова ДОЛЖНЫ появиться в тексте
- Если есть фото — ОБЯЗАТЕЛЬНО упомяни что-то про внешность (весело!)
- Если есть специальное правило (джокер) — выполни его
- Текст должен звучать НАТУРАЛЬНО, не как список слов
- Припев должен быть ЗАПОМИНАЮЩИМСЯ
"""


class LyricsGenerator:
    """Generator for AI-powered rap lyrics."""

    def __init__(self):
        self._client = get_gemini_client()

    @property
    def is_available(self) -> bool:
        """Check if lyrics generation is available."""
        return self._client.is_available

    async def generate_lyrics(
        self,
        selection: WordSelection,
        club_name: str = "VNVNC",
        photo_data: Optional[bytes] = None,
    ) -> Optional[GeneratedLyrics]:
        """Generate rap lyrics from word selection and optional photo.

        Args:
            selection: Selected words and settings
            club_name: Club name to mention (ENC/VNVNC)
            photo_data: Optional JPEG photo of the person for personalization

        Returns:
            GeneratedLyrics object or None on error
        """
        if not self._client.is_available:
            logger.warning("AI not available for lyrics generation")
            return self._fallback_lyrics(selection)

        try:
            # Get genre info
            genre_info = GENRES.get(selection.genre, GENRES["trap"])

            # Build the prompt
            prompt = self._build_prompt(selection, genre_info, club_name, has_photo=photo_data is not None)

            # Use Gemini 3 Flash (multimodal) for both text and image
            if photo_data:
                logger.info("Generating lyrics with photo personalization (Gemini 3 Flash)")
                response = await self._client.generate_with_image(
                    prompt=prompt,
                    image_data=photo_data,
                    model=GeminiModel.FLASH_3,  # Gemini 3 Flash is multimodal
                    system_instruction=RAP_LYRICIST_SYSTEM_PROMPT,
                    temperature=0.95,
                )
            else:
                logger.info("Generating lyrics without photo (Gemini 3 Flash)")
                response = await self._client.generate_text(
                    prompt=prompt,
                    model=GeminiModel.FLASH_3,
                    system_instruction=RAP_LYRICIST_SYSTEM_PROMPT,
                    temperature=0.95,
                    max_tokens=2048,
                )

            if response:
                return self._parse_response(response, selection.genre)

        except Exception as e:
            logger.error(f"Lyrics generation failed: {e}")

        return self._fallback_lyrics(selection)

    def _build_prompt(
        self,
        selection: WordSelection,
        genre_info: Dict[str, Any],
        club_name: str,
        has_photo: bool = False,
    ) -> str:
        """Build the lyrics generation prompt."""
        words_str = ", ".join(selection.words)

        parts = [
            f"Напиши рэп-трек используя эти слова: {words_str}",
            f"",
            f"Жанр: {genre_info['name_ru']} ({selection.genre})",
            f"BPM: {genre_info['bpm_range'][0]}-{genre_info['bpm_range'][1]}",
            f"Настроение: {genre_info['mood']}",
            f"",
            f"Клуб: {club_name} (можешь упомянуть)",
        ]

        if has_photo:
            parts.append("")
            parts.append("ВАЖНО: Я прикрепил фото человека! Посмотри на него и добавь в текст:")
            parts.append("- 2-3 весёлых упоминания его внешности (одежда, стиль, вайб)")
            parts.append("- Это должно быть комплиментарно и смешно!")
            parts.append("- Обыграй его образ креативно в рифмах")

        if selection.joker:
            parts.append(f"")
            parts.append(f"СПЕЦИАЛЬНОЕ ПРАВИЛО: {selection.joker}")

        parts.append("")
        parts.append("Сгенерируй трек и верни JSON:")

        return "\n".join(parts)

    def _parse_response(self, response: str, genre: str) -> Optional[GeneratedLyrics]:
        """Parse the AI response into GeneratedLyrics."""
        try:
            # Clean up response - remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                # Remove ```json and ``` markers
                cleaned = re.sub(r"^```\w*\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)

            data = json.loads(cleaned)

            lyrics = data.get("lyrics", {})

            return GeneratedLyrics(
                title=data.get("title", "Без названия"),
                artist=data.get("artist", "ARTIFACT AI"),
                genre=data.get("genre", genre),
                bpm=data.get("bpm", 140),
                mood=data.get("mood", "клубно"),
                hook=lyrics.get("hook", ""),
                verse1=lyrics.get("verse1", ""),
                verse2=lyrics.get("verse2"),
                tags=data.get("tags", []),
                one_liner=data.get("one_liner", "ARTIFACT BEATS"),
                raw_response=response,
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse lyrics JSON: {e}")
            # Try to extract text anyway
            return self._extract_text_fallback(response, genre)

        except Exception as e:
            logger.error(f"Lyrics parsing error: {e}")
            return None

    def _extract_text_fallback(self, response: str, genre: str) -> Optional[GeneratedLyrics]:
        """Extract lyrics from non-JSON response."""
        # Just use the raw text as lyrics
        lines = response.strip().split("\n")

        # Split roughly into hook and verse
        mid = len(lines) // 3
        hook_lines = lines[:mid] if mid > 0 else lines[:4]
        verse_lines = lines[mid:] if mid > 0 else lines[4:]

        return GeneratedLyrics(
            title="Без названия",
            artist="ARTIFACT AI",
            genre=genre,
            bpm=140,
            mood="клубно",
            hook="\n".join(hook_lines),
            verse1="\n".join(verse_lines),
            verse2=None,
            tags=["artifact", "ai", "rap"],
            one_liner="ARTIFACT BEATS",
            raw_response=response,
        )

    def _fallback_lyrics(self, selection: WordSelection) -> GeneratedLyrics:
        """Generate fallback lyrics when AI is unavailable."""
        import random

        words = selection.words
        genre_info = GENRES.get(selection.genre, GENRES["trap"])

        # Simple template-based fallback
        hooks = [
            f"{words[0]} на бите, {words[1]} в душе\n{words[2] if len(words) > 2 else 'движение'} это мы, ты слышишь?\nARTIFACT качает, это наш вайб\nНочь только началась, давай!",
            f"Эй, {words[0]}! Это {words[1]}!\n{words[2] if len(words) > 2 else 'Клуб'} горит, мы в ударе\nVNVNC до утра, это факт\nКачаем этот трек, это акт!",
        ]

        verses = [
            f"Захожу в клуб, вижу {words[0]}\nЭто мой мир, моя зона\n{words[1]} в кармане, {words[2] if len(words) > 2 else 'вайб'} в крови\nARTIFACT генерит, повтори",
            f"Бит качает, {words[0]} рядом\nМы на волне, это награда\n{words[1]} как символ этой ночи\nДвигай телом, стань жёстче",
        ]

        return GeneratedLyrics(
            title=f"{words[0].upper()} x {words[1].upper()}",
            artist="ARTIFACT AI",
            genre=selection.genre,
            bpm=random.randint(*genre_info["bpm_range"]),
            mood=genre_info["mood"],
            hook=random.choice(hooks),
            verse1=random.choice(verses),
            verse2=None,
            tags=words[:3] + ["artifact"],
            one_liner="ARTIFACT BEATS",
            raw_response="[fallback]",
        )


# Quick test
if __name__ == "__main__":
    import asyncio
    from artifact.modes.raptrack.wordbank import WordBank

    async def test():
        bank = WordBank()
        words = ["Oxxxymiron", "вайб", "клуб", "дерзкий"]
        selection = bank.create_selection(words, genre="trap")

        gen = LyricsGenerator()
        if gen.is_available:
            lyrics = await gen.generate_lyrics(selection)
            if lyrics:
                print(f"Title: {lyrics.title}")
                print(f"Artist: {lyrics.artist}")
                print(f"\nHook:\n{lyrics.hook}")
                print(f"\nVerse 1:\n{lyrics.verse1}")
        else:
            print("AI not available, using fallback")
            lyrics = gen._fallback_lyrics(selection)
            print(f"Title: {lyrics.title}")
            print(f"Hook:\n{lyrics.hook}")

    asyncio.run(test())
