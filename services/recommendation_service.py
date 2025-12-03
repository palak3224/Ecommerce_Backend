# services/recommendation_service.py
from datetime import datetime, timezone, timedelta
from flask import current_app
from sqlalchemy import desc, func, and_, or_
from sqlalchemy.orm import joinedload
from common.database import db
from common.cache import get_redis_client
from models.reel import Reel
from models.user_reel_like import UserReelLike
from models.user_reel_view import UserReelView
from models.user_merchant_follow import UserMerchantFollow
from models.user_category_preference import UserCategoryPreference
from models.product import Product
from models.product_stock import ProductStock
import json


class RecommendationService:
    """Service for generating personalized reel recommendations."""
    
    # Cache TTLs (in seconds)
    CACHE_TTL_RECOMMENDED = 300  # 5 minutes
    CACHE_TTL_TRENDING = 600  # 10 minutes
    CACHE_TTL_FOLLOWING = 300  # 5 minutes
    CACHE_TTL_PREFERENCES = 3600  # 1 hour
    
    @staticmethod
    def _get_redis_client():
        """Get Redis client, return None if unavailable."""
        try:
            return get_redis_client(current_app)
        except Exception:
            return None
    
    @staticmethod
    def _invalidate_user_cache(user_id):
        """Invalidate all recommendation caches for a user."""
        redis_client = RecommendationService._get_redis_client()
        if redis_client:
            try:
                # Delete all keys matching pattern
                pattern = f"feed:recommended:{user_id}:*"
                keys = redis_client.keys(pattern)
                if keys:
                    redis_client.delete(*keys)
                
                pattern = f"feed:following:{user_id}:*"
                keys = redis_client.keys(pattern)
                if keys:
                    redis_client.delete(*keys)
            except Exception:
                pass  # Silently fail if Redis unavailable
    
    @staticmethod
    def get_followed_merchant_reels(user_id, limit=20, exclude_reel_ids=None):
        """
        Get reels from merchants that the user follows.
        
        Args:
            user_id: User ID
            limit: Maximum number of reels to return
            exclude_reel_ids: Set of reel IDs to exclude
            
        Returns:
            List of Reel objects
        """
        if exclude_reel_ids is None:
            exclude_reel_ids = set()
        
        # Get followed merchant IDs
        follows = UserMerchantFollow.query.filter_by(user_id=user_id).all()
        merchant_ids = [f.merchant_id for f in follows]
        
        if not merchant_ids:
            return []
        
        # Get visible reels from followed merchants with eager loading
        query = Reel.get_visible_reels()
        query = query.options(
            joinedload(Reel.product).joinedload(Product.category),
            joinedload(Reel.merchant)
        )
        query = query.filter(Reel.merchant_id.in_(merchant_ids))
        
        if exclude_reel_ids:
            query = query.filter(~Reel.reel_id.in_(exclude_reel_ids))
        
        # Order by newest first
        query = query.order_by(desc(Reel.created_at))
        
        return query.limit(limit).all()
    
    @staticmethod
    def get_category_based_reels(user_id, limit=20, exclude_reel_ids=None):
        """
        Get reels based on user's category preferences.
        
        Args:
            user_id: User ID
            limit: Maximum number of reels to return
            exclude_reel_ids: Set of reel IDs to exclude
            
        Returns:
            List of Reel objects
        """
        if exclude_reel_ids is None:
            exclude_reel_ids = set()
        
        # Get user's category preferences (top 5)
        preferences = UserCategoryPreference.get_user_preferences(user_id, limit=5)
        
        if not preferences:
            return []
        
        category_ids = [p.category_id for p in preferences]
        
        # Get visible reels from preferred categories with eager loading
        query = Reel.get_visible_reels()
        query = query.options(
            joinedload(Reel.product).joinedload(Product.category),
            joinedload(Reel.merchant)
        )
        query = query.join(Product).filter(Product.category_id.in_(category_ids))
        
        if exclude_reel_ids:
            query = query.filter(~Reel.reel_id.in_(exclude_reel_ids))
        
        # Order by preference score (join with preferences) and created_at
        from sqlalchemy import case
        preference_scores = {p.category_id: float(p.preference_score) for p in preferences}
        
        # Order by category preference score and recency
        query = query.order_by(
            desc(case(preference_scores, value=Product.category_id, else_=0.0)),
            desc(Reel.created_at)
        )
        
        return query.limit(limit).all()
    
    @staticmethod
    def calculate_trending_score(reel, time_window_hours=24):
        """
        Calculate trending score for a reel.
        
        Formula: (likes*2 + views*1 + shares*3) / (hours_old + 1)
        
        Args:
            reel: Reel object
            time_window_hours: Time window in hours (default: 24)
            
        Returns:
            float: Trending score
        """
        now = datetime.now(timezone.utc)
        hours_old = (now - reel.created_at).total_seconds() / 3600
        
        # Only consider reels within time window
        if hours_old > time_window_hours:
            return 0.0
        
        # Engagement score
        engagement_score = (
            reel.likes_count * 2.0 +
            reel.views_count * 1.0 +
            reel.shares_count * 3.0
        )
        
        # Time decay factor (newer = better)
        time_decay = 1.0 / (hours_old + 1)
        
        # Trending score
        trending_score = (engagement_score * time_decay) / (hours_old + 1)
        
        # Boost for very recent reels (last 6 hours)
        if hours_old < 6:
            trending_score *= 1.5
        
        return trending_score
    
    @staticmethod
    def get_trending_reels(limit=20, time_window_hours=24, exclude_reel_ids=None):
        """
        Get trending reels based on engagement and recency.
        
        Args:
            limit: Maximum number of reels to return
            time_window_hours: Time window for trending (24h, 7d, 30d)
            exclude_reel_ids: Set of reel IDs to exclude
            
        Returns:
            List of Reel objects sorted by trending score
        """
        if exclude_reel_ids is None:
            exclude_reel_ids = set()
        
        # Get visible reels from last 7 days with eager loading
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)
        query = Reel.get_visible_reels()
        query = query.options(
            joinedload(Reel.product).joinedload(Product.category),
            joinedload(Reel.merchant)
        )
        query = query.filter(Reel.created_at >= cutoff_date)
        
        if exclude_reel_ids:
            query = query.filter(~Reel.reel_id.in_(exclude_reel_ids))
        
        # Get all reels and calculate scores
        reels = query.all()
        
        # Calculate trending scores
        scored_reels = []
        for reel in reels:
            score = RecommendationService.calculate_trending_score(reel, time_window_hours)
            if score > 0:
                scored_reels.append((score, reel))
        
        # Sort by score descending
        scored_reels.sort(key=lambda x: x[0], reverse=True)
        
        # Return top reels
        return [reel for _, reel in scored_reels[:limit]]
    
    @staticmethod
    def get_similar_user_reels(user_id, limit=20, exclude_reel_ids=None):
        """
        Get reels liked by users with similar preferences (collaborative filtering).
        
        Args:
            user_id: User ID
            limit: Maximum number of reels to return
            exclude_reel_ids: Set of reel IDs to exclude
            
        Returns:
            List of Reel objects
        """
        if exclude_reel_ids is None:
            exclude_reel_ids = set()
        
        # Get user's liked reels
        user_likes = UserReelLike.query.filter_by(user_id=user_id).all()
        user_liked_reel_ids = {like.reel_id for like in user_likes}
        
        if len(user_liked_reel_ids) < 3:
            # Need at least 3 likes to find similar users
            return []
        
        # Find users who liked at least 3 same reels
        similar_users = db.session.query(
            UserReelLike.user_id,
            func.count(UserReelLike.reel_id).label('common_likes')
        ).filter(
            UserReelLike.reel_id.in_(user_liked_reel_ids),
            UserReelLike.user_id != user_id
        ).group_by(UserReelLike.user_id).having(
            func.count(UserReelLike.reel_id) >= 3
        ).all()
        
        if not similar_users:
            return []
        
        similar_user_ids = [u[0] for u in similar_users]
        
        # Get reels liked by similar users (not yet liked by current user)
        similar_likes = UserReelLike.query.filter(
            UserReelLike.user_id.in_(similar_user_ids),
            ~UserReelLike.reel_id.in_(user_liked_reel_ids)
        ).all()
        
        if not similar_likes:
            return []
        
        # Get reel IDs
        similar_reel_ids = [like.reel_id for like in similar_likes]
        
        if exclude_reel_ids:
            similar_reel_ids = [rid for rid in similar_reel_ids if rid not in exclude_reel_ids]
        
        # Get visible reels with eager loading
        query = Reel.get_visible_reels()
        query = query.options(
            joinedload(Reel.product).joinedload(Product.category),
            joinedload(Reel.merchant)
        )
        query = query.filter(Reel.reel_id.in_(similar_reel_ids))
        query = query.order_by(desc(Reel.likes_count), desc(Reel.created_at))
        
        return query.limit(limit).all()
    
    @staticmethod
    def calculate_final_reel_score(reel, user_id, context):
        """
        Calculate final score for a reel in personalized feed.
        
        Args:
            reel: Reel object
            user_id: User ID
            context: Dict with pre-calculated values (is_followed_merchant, category_preference_score, trending_score, similar_user_score)
            
        Returns:
            float: Final score
        """
        score = 0.0
        
        # Tier 1: Followed Merchant (weight: 10.0)
        if context.get('is_followed_merchant'):
            score += 10.0
            # Extra boost for new reels (last 24 hours)
            hours_old = (datetime.now(timezone.utc) - reel.created_at).total_seconds() / 3600
            if hours_old < 24:
                score += 2.0
        
        # Tier 2: Category Match (weight: 5.0)
        category_score = context.get('category_preference_score', 0.0)
        score += category_score * 5.0
        
        # Tier 3: Trending (weight: 3.0)
        trending_score = context.get('trending_score', 0.0)
        score += trending_score * 3.0
        
        # Tier 4: Similar Users (weight: 2.0)
        similar_user_score = context.get('similar_user_score', 0.0)
        score += similar_user_score * 2.0
        
        # Tier 5: Recency (weight: 1.0)
        hours_old = (datetime.now(timezone.utc) - reel.created_at).total_seconds() / 3600
        if hours_old < 24:
            score += 1.0 * (1.0 - hours_old / 24)  # Decay over 24 hours
        
        # Penalties
        if context.get('already_shown'):
            score *= 0.1  # Heavy penalty for duplicates
        
        return score
    
    @staticmethod
    def build_reel_context(reel, user_id):
        """
        Build context dictionary for a reel.
        
        Args:
            reel: Reel object
            user_id: User ID
            
        Returns:
            dict: Context with pre-calculated values
        """
        context = {
            'is_followed_merchant': False,
            'category_preference_score': 0.0,
            'trending_score': 0.0,
            'similar_user_score': 0.0,
            'already_shown': False
        }
        
        # Check if merchant is followed
        if UserMerchantFollow.is_following(user_id, reel.merchant_id):
            context['is_followed_merchant'] = True
        
        # Get category preference score with time decay
        if reel.product and reel.product.category_id:
            pref = UserCategoryPreference.query.filter_by(
                user_id=user_id,
                category_id=reel.product.category_id
            ).first()
            if pref:
                base_score = float(pref.preference_score)
                # Apply time decay: older interactions weigh less
                if pref.last_interaction_at:
                    days_since_interaction = (datetime.now(timezone.utc) - pref.last_interaction_at).days
                    # Decay factor: 1.0 for today, 0.5 after 30 days, 0.1 after 90 days
                    if days_since_interaction <= 7:
                        decay_factor = 1.0
                    elif days_since_interaction <= 30:
                        decay_factor = 1.0 - (days_since_interaction - 7) / 46.0  # Linear decay from 1.0 to 0.5
                    else:
                        decay_factor = max(0.1, 0.5 - (days_since_interaction - 30) / 120.0)  # Further decay to 0.1
                    context['category_preference_score'] = base_score * decay_factor
                else:
                    context['category_preference_score'] = base_score
                
                # Add view duration weighting if user has viewed this reel
                from models.user_reel_view import UserReelView
                user_view = UserReelView.query.filter_by(
                    user_id=user_id,
                    reel_id=reel.reel_id
                ).first()
                if user_view and user_view.view_duration and reel.duration_seconds and reel.duration_seconds > 0:
                    watch_percentage = min(1.0, user_view.view_duration / reel.duration_seconds)
                    # Boost score based on watch percentage: full watch (80%+) = +0.2, partial (50-80%) = +0.1
                    if watch_percentage >= 0.8:
                        context['category_preference_score'] += 0.2
                    elif watch_percentage >= 0.5:
                        context['category_preference_score'] += 0.1
                    # Cap at 1.0
                    context['category_preference_score'] = min(1.0, context['category_preference_score'])
        
        # Calculate trending score
        context['trending_score'] = RecommendationService.calculate_trending_score(reel, 24)
        
        # Similar user score (simplified - would need more complex calculation)
        # For now, set to 1.0 if reel is from similar users (calculated elsewhere)
        context['similar_user_score'] = 1.0  # Will be set properly in get_personalized_feed
        
        return context
    
    @staticmethod
    def get_personalized_feed(user_id, page=1, per_page=20):
        """
        Generate personalized feed for user.
        
        Mixes all tiers: 40% followed, 30% category, 20% trending, 10% similar, fill with general.
        
        Args:
            user_id: User ID
            page: Page number
            per_page: Items per page
            
        Returns:
            tuple: (list of Reel objects, dict with feed info)
        """
        # Check cache
        redis_client = RecommendationService._get_redis_client()
        cache_key = f"feed:recommended:{user_id}:{page}:{per_page}"
        
        if redis_client:
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    # Convert reel IDs back to Reel objects with eager loading
                    reel_ids = data['reel_ids']
                    reels = Reel.query.options(
                        joinedload(Reel.product).joinedload(Product.category),
                        joinedload(Reel.merchant)
                    ).filter(Reel.reel_id.in_(reel_ids)).all()
                    # Sort by original order
                    reel_dict = {r.reel_id: r for r in reels}
                    reels = [reel_dict[rid] for rid in reel_ids if rid in reel_dict]
                    feed_info = data['feed_info']
                    return reels, feed_info
            except Exception:
                pass  # Continue if cache fails
        
        seen_reel_ids = set()
        feed_reels = []
        tiers_used = []
        merchant_counts = {}
        category_counts = {}
        
        # Tier 1: Followed Merchants (40%) with diversity
        followed_limit = int(per_page * 0.4)
        followed_reels = RecommendationService.get_followed_merchant_reels(
            user_id, limit=followed_limit * 2, exclude_reel_ids=seen_reel_ids  # Get more to apply diversity
        )
        if followed_reels:
            tiers_used.append('followed')
            for reel in followed_reels:
                if reel.reel_id not in seen_reel_ids:
                    # Apply diversity: max 3 per merchant
                    merchant_id = reel.merchant_id
                    if merchant_id not in merchant_counts:
                        merchant_counts[merchant_id] = 0
                    if merchant_counts[merchant_id] < 3:
                        feed_reels.append(reel)
                        seen_reel_ids.add(reel.reel_id)
                        merchant_counts[merchant_id] += 1
                    if len(feed_reels) >= followed_limit:
                        break
        
        # Tier 2: Category-Based (30%) with diversity
        category_limit = int(per_page * 0.3)
        category_reels = RecommendationService.get_category_based_reels(
            user_id, limit=category_limit * 2, exclude_reel_ids=seen_reel_ids  # Get more to apply diversity
        )
        if category_reels:
            tiers_used.append('category')
            for reel in category_reels:
                if reel.reel_id not in seen_reel_ids:
                    # Apply diversity: max 5 per category
                    category_id = reel.product.category_id if reel.product else None
                    if category_id:
                        if category_id not in category_counts:
                            category_counts[category_id] = 0
                        if category_counts[category_id] >= 5:
                            continue
                    feed_reels.append(reel)
                    seen_reel_ids.add(reel.reel_id)
                    if category_id:
                        category_counts[category_id] = category_counts.get(category_id, 0) + 1
                    if len(feed_reels) >= (followed_limit + category_limit):
                        break
        
        # Tier 3: Trending (20%)
        trending_limit = int(per_page * 0.2)
        trending_reels = RecommendationService.get_trending_reels(
            limit=trending_limit, exclude_reel_ids=seen_reel_ids
        )
        if trending_reels:
            tiers_used.append('trending')
            for reel in trending_reels:
                if reel.reel_id not in seen_reel_ids:
                    feed_reels.append(reel)
                    seen_reel_ids.add(reel.reel_id)
        
        # Tier 4: Similar Users (10%)
        similar_limit = int(per_page * 0.1)
        similar_reels = RecommendationService.get_similar_user_reels(
            user_id, limit=similar_limit, exclude_reel_ids=seen_reel_ids
        )
        if similar_reels:
            tiers_used.append('similar_users')
            for reel in similar_reels:
                if reel.reel_id not in seen_reel_ids:
                    feed_reels.append(reel)
                    seen_reel_ids.add(reel.reel_id)
        
        # Tier 5: General Feed (fill remaining) with eager loading
        remaining = per_page - len(feed_reels)
        if remaining > 0:
            query = Reel.get_visible_reels()
            query = query.options(
                joinedload(Reel.product).joinedload(Product.category),
                joinedload(Reel.merchant)
            )
            if seen_reel_ids:
                query = query.filter(~Reel.reel_id.in_(seen_reel_ids))
            query = query.order_by(desc(Reel.created_at))
            general_reels = query.limit(remaining).all()
            if general_reels:
                tiers_used.append('general')
                feed_reels.extend(general_reels)
        
        # Calculate scores and sort
        scored_reels = []
        for reel in feed_reels:
            context = RecommendationService.build_reel_context(reel, user_id)
            # Mark as similar if from similar users tier
            if reel in similar_reels:
                context['similar_user_score'] = 1.0
            score = RecommendationService.calculate_final_reel_score(reel, user_id, context)
            scored_reels.append((score, reel))
        
        # Sort by score descending
        scored_reels.sort(key=lambda x: x[0], reverse=True)
        
        # Apply additional diversity constraints during final selection
        final_reels = []
        final_merchant_counts = {}
        final_category_counts = {}
        
        for score, reel in scored_reels:
            # Check merchant diversity (max 3 per merchant in final feed)
            merchant_id = reel.merchant_id
            if merchant_id not in final_merchant_counts:
                final_merchant_counts[merchant_id] = 0
            if final_merchant_counts[merchant_id] >= 3:
                continue  # Skip if already have 3 from this merchant
            
            # Check category diversity (max 5 per category in final feed)
            category_id = reel.product.category_id if reel.product else None
            if category_id:
                if category_id not in final_category_counts:
                    final_category_counts[category_id] = 0
                if final_category_counts[category_id] >= 5:
                    continue  # Skip if already have 5 from this category
            
            # Add reel
            final_reels.append(reel)
            final_merchant_counts[merchant_id] += 1
            if category_id:
                final_category_counts[category_id] += 1
            
            # Stop if we have enough reels
            if len(final_reels) >= per_page:
                break
        
        # Paginate
        start = (page - 1) * per_page
        end = start + per_page
        paginated_reels = final_reels[start:end]
        
        # Build feed info
        feed_info = {
            'feed_type': 'recommended',
            'tiers_used': tiers_used,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Cache result
        if redis_client:
            try:
                cache_data = {
                    'reel_ids': [r.reel_id for r in paginated_reels],
                    'feed_info': feed_info
                }
                redis_client.setex(
                    cache_key,
                    RecommendationService.CACHE_TTL_RECOMMENDED,
                    json.dumps(cache_data)
                )
            except Exception:
                pass  # Silently fail if cache fails
        
        return paginated_reels, feed_info
    
    @staticmethod
    def _get_cold_start_feed(user_id, page=1, per_page=20):
        """
        Generate feed for new users with < 3 interactions.
        Returns 70% trending + 30% category diversity.
        
        Args:
            user_id: User ID
            page: Page number
            per_page: Items per page
            
        Returns:
            tuple: (list of Reel objects, dict with feed info)
        """
        seen_reel_ids = set()
        feed_reels = []
        
        # 70% trending
        trending_limit = int(per_page * 0.7)
        trending_reels = RecommendationService.get_trending_reels(
            limit=trending_limit, exclude_reel_ids=seen_reel_ids
        )
        for reel in trending_reels:
            feed_reels.append(reel)
            seen_reel_ids.add(reel.reel_id)
        
        # 30% category diversity (from top categories)
        category_limit = int(per_page * 0.3)
        category_reels = RecommendationService.get_category_based_reels(
            user_id, limit=category_limit, exclude_reel_ids=seen_reel_ids
        )
        for reel in category_reels:
            feed_reels.append(reel)
            seen_reel_ids.add(reel.reel_id)
        
        # Fill remaining with general feed
        remaining = per_page - len(feed_reels)
        if remaining > 0:
            query = Reel.get_visible_reels()
            query = query.options(
                joinedload(Reel.product).joinedload(Product.category),
                joinedload(Reel.merchant)
            )
            if seen_reel_ids:
                query = query.filter(~Reel.reel_id.in_(seen_reel_ids))
            query = query.order_by(desc(Reel.created_at))
            general_reels = query.limit(remaining).all()
            feed_reels.extend(general_reels)
        
        # Paginate
        start = (page - 1) * per_page
        end = start + per_page
        paginated_reels = feed_reels[start:end]
        
        feed_info = {
            'feed_type': 'recommended',
            'feed_variant': 'cold_start',
            'tiers_used': ['trending', 'category', 'general'],
            'generated_at': datetime.now(timezone.utc).isoformat()
        }
        
        return paginated_reels, feed_info

