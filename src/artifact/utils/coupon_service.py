"""Coupon service for arcade prizes.

This service creates coupons locally using the Telegram bot's coupon store.
Coupons can be validated by staff using the bot's /check and /redeem commands.
"""

import logging
import random
import string
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Code format: VNVNC-XXXX-XXXX-XXXX
# Using characters that are easy to read (no O/0, I/1/l confusion)
CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_coupon_code() -> str:
    """Generate a unique coupon code in VNVNC-XXXX-XXXX-XXXX format."""
    parts = []
    for _ in range(3):
        part = "".join(random.choices(CODE_CHARS, k=4))
        parts.append(part)
    return f"VNVNC-{'-'.join(parts)}"


@dataclass
class CouponResult:
    """Result of coupon registration."""
    success: bool
    coupon_code: Optional[str] = None
    prize_label: Optional[str] = None
    prize_description: Optional[str] = None
    expires_at: Optional[str] = None
    error: Optional[str] = None


class CouponService:
    """Service for creating and managing arcade prize coupons.

    Prize types available:
        - COCKTL: Free cocktail
        - SHOTFR: Free shot
        - DEP5K: 5000₽ deposit
        - DEP10K: 10000₽ deposit
        - MERCHX: VNVNC merchandise
    """

    # Prize type constants
    PRIZE_COCKTAIL = "COCKTL"
    PRIZE_SHOT = "SHOTFR"
    PRIZE_DEPOSIT_5K = "DEP5K"
    PRIZE_DEPOSIT_10K = "DEP10K"
    PRIZE_MERCH = "MERCHX"

    # Prize labels (Russian)
    PRIZE_LABELS = {
        "COCKTL": "Бесплатный коктейль",
        "SHOTFR": "Бесплатный шот",
        "DEP5K": "Депозит 5000₽",
        "DEP10K": "Депозит 10000₽",
        "MERCHX": "Мерч VNVNC",
    }

    # Prize descriptions
    PRIZE_DESCRIPTIONS = {
        "COCKTL": "Бесплатный коктейль на выбор",
        "SHOTFR": "Бесплатный шот на выбор",
        "DEP5K": "5000₽ на депозит",
        "DEP10K": "10000₽ на депозит",
        "MERCHX": "Мерч VNVNC на выбор",
    }

    def __init__(self):
        """Initialize coupon service."""
        self._bot = None

    def _get_bot(self):
        """Get the arcade bot instance (lazy load to avoid circular import)."""
        if self._bot is None:
            from artifact.telegram import get_arcade_bot
            self._bot = get_arcade_bot()
        return self._bot

    async def register_coupon(
        self,
        prize_type: str,
        source: str,
        guest_name: Optional[str] = None,
    ) -> CouponResult:
        """Register a new coupon.

        Args:
            prize_type: Prize type ID (COCKTL, SHOTFR, etc.)
            source: Source identifier (e.g., ARCADE_QUIZ, ARCADE_SQUID)
            guest_name: Optional name of the guest who won

        Returns:
            CouponResult with coupon code or error
        """
        try:
            # Generate unique code
            code = generate_coupon_code()

            # Get prize label and description
            prize_label = self.PRIZE_LABELS.get(prize_type, prize_type)
            prize_description = self.PRIZE_DESCRIPTIONS.get(prize_type, "")

            # Calculate expiration (7 days from now)
            expires_at = (datetime.now() + timedelta(days=7)).isoformat()

            # Create coupon via bot
            bot = self._get_bot()
            coupon = bot.create_coupon(
                code=code,
                prize_type=prize_type,
                source=source,
            )

            logger.info(f"Coupon created: {code} for {prize_type} ({source})")

            return CouponResult(
                success=True,
                coupon_code=code,
                prize_label=prize_label,
                prize_description=prize_description,
                expires_at=expires_at,
            )

        except Exception as e:
            logger.exception(f"Failed to create coupon: {e}")
            return CouponResult(
                success=False,
                error=str(e),
            )

    async def register_quiz_win(self, guest_name: Optional[str] = None) -> CouponResult:
        """Register a quiz mode win (free cocktail).

        Args:
            guest_name: Optional name of the winner

        Returns:
            CouponResult with coupon code or error
        """
        return await self.register_coupon(
            prize_type=self.PRIZE_COCKTAIL,
            source="ARCADE_QUIZ",
            guest_name=guest_name,
        )

    async def register_squid_win(self, guest_name: Optional[str] = None) -> CouponResult:
        """Register a squid game mode win (free cocktail).

        Args:
            guest_name: Optional name of the winner

        Returns:
            CouponResult with coupon code or error
        """
        return await self.register_coupon(
            prize_type=self.PRIZE_COCKTAIL,
            source="ARCADE_SQUID",
            guest_name=guest_name,
        )

    async def register_shot_win(
        self, source: str = "ARCADE", guest_name: Optional[str] = None
    ) -> CouponResult:
        """Register a free shot prize.

        Args:
            source: Source identifier (e.g., ARCADE_SQUID)
            guest_name: Optional name of the winner

        Returns:
            CouponResult with coupon code or error
        """
        return await self.register_coupon(
            prize_type=self.PRIZE_SHOT,
            source=source,
            guest_name=guest_name,
        )

    async def close(self) -> None:
        """Cleanup (no-op for local service)."""
        pass


# Global instance for easy access
_coupon_service: Optional[CouponService] = None


def get_coupon_service() -> CouponService:
    """Get or create global coupon service instance."""
    global _coupon_service
    if _coupon_service is None:
        _coupon_service = CouponService()
    return _coupon_service
