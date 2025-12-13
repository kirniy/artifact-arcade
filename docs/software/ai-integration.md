# AI Integration

## Overview

ARTIFACT integrates two Gemini AI models for the AI Prophet mode:
- **Gemini 2.5 Flash**: Generates personalized text predictions from photos and answers
- **Gemini 3.0 Pro**: Creates black-and-white caricature images

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AI Service                              │
│   Singleton Client → Request Queue → Response Handler        │
└────────────────────────────┬────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                                     │
    ┌─────▼─────┐                        ┌─────▼─────┐
    │  Gemini   │                        │  Gemini   │
    │ 2.5 Flash │                        │  3.0 Pro  │
    │(Predictor)│                        │(Caricature)│
    └───────────┘                        └───────────┘
```

## Gemini 2.5 Flash (Predictions)

### Purpose

Generate personalized fortune predictions based on:
- User photo (for appearance-based insights)
- Binary question answers (personality indicators)
- Selected mode context (fortune style)

### Implementation Pattern

Based on the voicio project's Gemini client:

```python
from google import genai
from google.genai import types

class GeminiClient:
    """Singleton Gemini client with retry logic."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = genai.Client(
                api_key=os.environ["GEMINI_API_KEY"]
            )
        return cls._instance

    async def generate_prediction(
        self,
        photo: bytes,
        answers: list[bool],
        mode: str
    ) -> str:
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_budget=1024
            ),
            temperature=0.9,
            max_output_tokens=500
        )

        prompt = self._build_prompt(answers, mode)

        response = await self._client.aio.models.generate_content(
            model="gemini-2.5-flash-preview-05-20",
            contents=[
                types.Part.from_bytes(photo, mime_type="image/jpeg"),
                prompt
            ],
            config=config
        )

        return response.text
```

### Request Configuration

| Parameter | Value | Purpose |
|-----------|-------|---------|
| model | gemini-2.5-flash-preview-05-20 | Fast multimodal generation |
| thinking_budget | 1024 | Enable reasoning for better predictions |
| temperature | 0.9 | Creative, varied outputs |
| max_output_tokens | 500 | Concise predictions |
| timeout | 300s | Allow for complex processing |

### Prompt Engineering

**System Context**:
```
You are a mystical fortune teller at an arcade machine. Based on the
person's photo and their answers to binary questions, provide a
creative, entertaining, and positive fortune prediction.

Keep predictions:
- Fun and engaging
- Personalized to appearance details
- Reflecting their answer choices
- Appropriate for all ages
- In Russian language
```

**Question Integration**:
```
The person answered these questions:
1. "Are you more of a dreamer than a doer?" - {Yes/No}
2. "Do you prefer quiet nights over parties?" - {Yes/No}
3. "Would you take a risk for adventure?" - {Yes/No}

Based on their {answers} and appearance, predict their fortune.
```

### Error Handling

```python
async def generate_with_retry(self, ...):
    for attempt in range(3):
        try:
            return await self._generate(...)
        except ServiceUnavailableError:
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
            else:
                raise
        except InvalidRequestError:
            # Don't retry invalid requests
            raise
```

## Gemini 3.0 Pro (Caricatures)

### Purpose

Generate black-and-white sketch caricatures from user photos for thermal printing.

### Implementation Pattern

Based on the nano-banana-pro project's approach:

```python
import aiohttp

class CaricatureGenerator:
    """Generate caricatures using Gemini 3.0 Pro image generation."""

    API_URL = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-3-pro-image-preview:generateContent"
    )

    async def generate(self, photo: bytes) -> bytes:
        prompt = (
            "Create a black-and-white sketch/doodle caricature of this "
            "person on a pure white background. Style: simple line art, "
            "exaggerated features, friendly and fun. No color, no shading, "
            "just clean black lines on white."
        )

        async with aiohttp.ClientSession() as session:
            response = await session.post(
                self.API_URL,
                params={"key": os.environ["GEMINI_API_KEY"]},
                json={
                    "contents": [{
                        "parts": [
                            {"text": prompt},
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": base64.b64encode(photo).decode()
                                }
                            }
                        ]
                    }],
                    "generationConfig": {
                        "responseModalities": ["image", "text"],
                        "responseMimeType": "image/png"
                    }
                },
                timeout=aiohttp.ClientTimeout(total=480)
            )

            result = await response.json()
            image_data = result["candidates"][0]["content"]["parts"][0]
            return base64.b64decode(image_data["inline_data"]["data"])
```

### Request Configuration

| Parameter | Value | Purpose |
|-----------|-------|---------|
| model | gemini-3-pro-image-preview | Image generation capability |
| responseModalities | ["image", "text"] | Get image output |
| responseMimeType | image/png | PNG for processing |
| timeout | 480s (8 min) | Long generation time |
| aspect_ratio | 1:1 | Square for thermal printer |

### Prompt Optimization

**For Thermal Printing**:
```
Critical requirements:
- Pure black lines on pure white background
- No gradients or shading (thermal can't print)
- High contrast for clear printing
- Simple line art style
- Exaggerated but recognizable features
```

**Style Variations**:
- `cartoon`: Animated style, big eyes
- `sketch`: Hand-drawn pencil look
- `caricature`: Exaggerated proportions
- `minimal`: Few lines, abstract

## AI Prophet Mode Flow

### Complete Sequence

```
┌─────────────┐
│   Start     │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│   Camera    │────▶│ Take Photo  │
│   Intro     │     │ (countdown) │
└─────────────┘     └──────┬──────┘
                           │
                           ▼
┌─────────────┐     ┌─────────────┐
│  Question 1 │◀────│  Questions  │
│  Yes / No   │     │  (3-5 Q's)  │
└──────┬──────┘     └─────────────┘
       │
       ▼ (repeat for each question)
       │
┌──────▼──────┐
│ Processing  │────────────────────┐
│ Animation   │                    │
└──────┬──────┘                    │
       │                           │
       ▼                           ▼
┌─────────────┐           ┌─────────────┐
│   Gemini    │           │   Gemini    │
│  2.5 Flash  │           │   3.0 Pro   │
│ (prediction)│           │ (caricature)│
└──────┬──────┘           └──────┬──────┘
       │                         │
       └────────────┬────────────┘
                    │ (parallel)
                    ▼
           ┌─────────────┐
           │   Result    │
           │   Reveal    │
           └──────┬──────┘
                  │
                  ▼
           ┌─────────────┐
           │   Print?    │
           │   L=No R=Yes│
           └──────┬──────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
  ┌───────────┐      ┌───────────┐
  │   Skip    │      │   Print   │
  │  (done)   │      │  Receipt  │
  └───────────┘      └───────────┘
```

### Timing Budget

| Phase | Duration | Display Activity |
|-------|----------|------------------|
| Camera intro | 2s | "Look at camera" animation |
| Countdown | 3s | 3-2-1 countdown |
| Photo capture | 0.5s | Flash effect |
| Each question | 5s max | Question + buttons highlight |
| Processing | 10-30s | AI animation + progress |
| Result reveal | 2s | Reveal animation |
| Result display | 10s | Show prediction |
| Print prompt | 5s | "Print? L/R" |
| Printing | 15s | Print progress |

## Parallel Processing

### Optimization Strategy

Start both AI requests simultaneously after photo + answers collected:

```python
async def process_ai_prophet(photo: bytes, answers: list[bool]):
    # Launch both AI tasks in parallel
    prediction_task = asyncio.create_task(
        gemini_client.generate_prediction(photo, answers, "fortune")
    )
    caricature_task = asyncio.create_task(
        caricature_generator.generate(photo)
    )

    # Wait for both to complete
    prediction, caricature = await asyncio.gather(
        prediction_task,
        caricature_task,
        return_exceptions=True
    )

    # Handle partial failures gracefully
    if isinstance(prediction, Exception):
        prediction = get_fallback_prediction()
    if isinstance(caricature, Exception):
        caricature = None  # Print without caricature

    return prediction, caricature
```

## Caching Strategy

### Photo Hash Caching

```python
def get_photo_hash(photo: bytes) -> str:
    return hashlib.md5(photo).hexdigest()[:16]

cache = {}  # In production: Redis or file-based

async def get_or_generate(photo, answers):
    key = f"{get_photo_hash(photo)}_{hash(tuple(answers))}"
    if key in cache:
        return cache[key]

    result = await process_ai_prophet(photo, answers)
    cache[key] = result
    return result
```

### Cache Invalidation

- Cache expires after 24 hours
- Maximum 100 cached results
- LRU eviction policy

## Fallback Handling

### Prediction Fallbacks

If Gemini 2.5 Flash fails:
1. Retry with exponential backoff (3 attempts)
2. Use pre-written fortune from database
3. Generate based on answers only (no photo analysis)

### Caricature Fallbacks

If Gemini 3.0 Pro fails:
1. Retry once after 30s
2. Print receipt without caricature
3. Use placeholder illustration

### Offline Mode

If no internet connection:
- Detect via connectivity check
- Use local prediction database
- Skip caricature generation
- Show "offline mode" indicator

## Security Considerations

### API Key Protection

```python
# Load from environment only
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ConfigurationError("GEMINI_API_KEY not set")

# Never log or expose key
# Never include in error messages
```

### Photo Privacy

- Photos processed in memory only
- No persistent storage of photos
- Cache uses hashes, not actual photos
- Clear photo data after session

### Rate Limiting

```python
class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = []

    async def acquire(self):
        now = time.time()
        self.requests = [r for r in self.requests if now - r < self.window]
        if len(self.requests) >= self.max_requests:
            raise RateLimitExceeded()
        self.requests.append(now)
```

## Testing

### Mock AI Service

```python
class MockGeminiClient:
    async def generate_prediction(self, photo, answers, mode):
        await asyncio.sleep(0.5)  # Simulate latency
        return "Your future holds great adventures!"

class MockCaricatureGenerator:
    async def generate(self, photo):
        await asyncio.sleep(1.0)
        # Return test image
        return Path("assets/test/mock_caricature.png").read_bytes()
```

### Test Cases

1. **Happy path**: Photo + answers → prediction + caricature
2. **Prediction timeout**: Falls back to database
3. **Caricature failure**: Prints without image
4. **Both fail**: Uses fallback prediction, no image
5. **Rate limited**: Shows "busy" message
6. **Invalid photo**: Error handling
