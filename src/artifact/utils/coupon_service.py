"""Coupon service for registering arcade prizes with vnvnc-bot.

This service communicates with the vnvnc-bot API to register coupons
that can be validated by staff using the wheel of fortune validator.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional, Callable

import aiohttp

logger = logging.getLogger(__name__)


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
    """Service for registering coupons with vnvnc-bot.

    Prize types available:
        - COCKTL: Free cocktail
        - SHOTFR: Free shot
        - DEP5K: 5000₽ deposit
        - DEP10K: 10000₽ deposit
        - MERCHX: VNVNC merchandise
    """

    # API configuration
    DEFAULT_API_URL = "https://vnvnc-bot.fly.dev"
    DEFAULT_API_KEY = "arcade-secret-key-2025"

    # Prize type constants
    PRIZE_COCKTAIL = "COCKTL"
    PRIZE_SHOT = "SHOTFR"
    PRIZE_DEPOSIT_5K = "DEP5K"
    PRIZE_DEPOSIT_10K = "DEP10K"
    PRIZE_MERCH = "MERCHX"

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """Initialize coupon service.

        Args:
            api_url: Base URL of vnvnc-bot API
            api_key: API key for authentication
        """
        self._api_url = api_url or os.environ.get("VNVNC_API_URL", self.DEFAULT_API_URL)
        self._api_key = api_key or os.environ.get("VNVNC_API_KEY", self.DEFAULT_API_KEY)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self._session

    async def register_coupon(
        self,
        prize_type: str,
        source: str,
        guest_name: Optional[str] = None,
    ) -> CouponResult:
        """Register a coupon with vnvnc-bot.

        Args:
            prize_type: Prize type ID (COCKTL, SHOTFR, etc.)
            source: Source identifier (e.g., ARCADE_QUIZ, ARCADE_SQUID)
            guest_name: Optional name of the guest who won

        Returns:
            CouponResult with coupon code or error
        """
        try:
            session = await self._get_session()

            payload = {
                "prize_type": prize_type,
                "source": source,
            }
            if guest_name:
                payload["guest_name"] = guest_name

            url = f"{self._api_url}/api/arcade/register"

            async with session.post(url, json=payload) as response:
                data = await response.json()

                if response.status == 200 and data.get("success"):
                    logger.info(
                        f"Coupon registered: {data.get('coupon_code')} "
                        f"for {prize_type} ({source})"
                    )
                    return CouponResult(
                        success=True,
                        coupon_code=data.get("coupon_code"),
                        prize_label=data.get("prize_label"),
                        prize_description=data.get("prize_description"),
                        expires_at=data.get("expires_at"),
                    )
                else:
                    error = data.get("error", f"HTTP {response.status}")
                    logger.error(f"Failed to register coupon: {error}")
                    return CouponResult(
                        success=False,
                        error=error,
                    )

        except asyncio.TimeoutError:
            logger.error("Timeout registering coupon")
            return CouponResult(success=False, error="TIMEOUT")
        except aiohttp.ClientError as e:
            logger.error(f"Network error registering coupon: {e}")
            return CouponResult(success=False, error="NETWORK_ERROR")
        except Exception as e:
            logger.exception(f"Unexpected error registering coupon: {e}")
            return CouponResult(success=False, error=str(e))

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

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None


# Global instance for easy access
_coupon_service: Optional[CouponService] = None


def get_coupon_service() -> CouponService:
    """Get or create global coupon service instance."""
    global _coupon_service
    if _coupon_service is None:
        _coupon_service = CouponService()
    return _coupon_service
