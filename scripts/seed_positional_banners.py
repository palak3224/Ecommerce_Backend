"""
Seed the positional hero banners (right sidebar + two bottom banners) into the
`carousels` table so the homepage keeps showing the current images after the
RightCarousel / Bottom1Carousel / Bottom2Carousel components were made dynamic.

These slots have no brand/product target, so target_id is 0 and the click link
(shareable_link) is left empty. Admins can edit/replace them afterwards from
Superadmin -> Homepage Settings -> "Side & Bottom Banners".

Idempotent: a slot is skipped if it already has at least one active banner, so
re-running will not create duplicates.

Usage:
    python scripts/seed_positional_banners.py
"""

from app import create_app
from common.database import db
from models.carousel import Carousel

# type -> (orientation, [image_url, ...]) in display order.
# URLs are the exact images previously hardcoded in the frontend components.
SEED_DATA = {
    "sidebar_right": (
        "vertical",
        [
            "https://res.cloudinary.com/do3vxz4gw/image/upload/v1751544913/svg_assets/rightcrousel_Image3.svg",
            "https://res.cloudinary.com/do3vxz4gw/image/upload/v1751544854/svg_assets/rightcrousel_Image2.svg",
            "https://res.cloudinary.com/do3vxz4gw/image/upload/v1751544854/svg_assets/rightcrousel_Image3.svg",
        ],
    ),
    "bottom_left": (
        "horizontal",
        [
            "https://res.cloudinary.com/djimsqy66/image/upload/v1770105245/banner2_xzrfp0.jpg",
            "https://res.cloudinary.com/djimsqy66/image/upload/v1770105246/banner5_y4j38t.jpg",
            "https://res.cloudinary.com/djimsqy66/image/upload/v1770105246/banner4_me34jb.jpg",
        ],
    ),
    "bottom_right": (
        "horizontal",
        [
            "https://res.cloudinary.com/djimsqy66/image/upload/v1770105245/banner2_xzrfp0.jpg",
            "https://res.cloudinary.com/djimsqy66/image/upload/v1770105243/banner3_ohwtha.jpg",
            "https://res.cloudinary.com/djimsqy66/image/upload/v1770105272/ProductBanner_etnova.jpg",
        ],
    ),
}


def seed():
    app = create_app()
    with app.app_context():
        total_created = 0
        for slot_type, (orientation, urls) in SEED_DATA.items():
            existing = Carousel.query.filter_by(
                type=slot_type, deleted_at=None
            ).count()
            if existing:
                print(f"[skip] '{slot_type}' already has {existing} banner(s); leaving untouched.")
                continue

            for order, url in enumerate(urls):
                banner = Carousel(
                    type=slot_type,
                    orientation=orientation,
                    image_url=url,
                    target_id=0,
                    display_order=order,
                    is_active=True,
                    shareable_link=None,
                )
                db.session.add(banner)
                total_created += 1
            print(f"[seed] '{slot_type}': queued {len(urls)} banner(s).")

        if total_created:
            db.session.commit()
            print(f"\nDone. Created {total_created} banner(s).")
        else:
            print("\nNothing to do. All slots already seeded.")


if __name__ == "__main__":
    seed()
