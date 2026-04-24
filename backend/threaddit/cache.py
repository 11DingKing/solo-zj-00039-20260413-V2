import logging
import redis
from threaddit.config import REDIS_URL

logger = logging.getLogger(__name__)

VOTE_COUNT_KEY_PREFIX = "vote:count:"
USER_VOTES_KEY_PREFIX = "user:votes:"
VOTE_COUNT_TTL = 86400

_redis_client = None


def get_redis_client():
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=5, socket_connect_timeout=5)
            _redis_client.ping()
        except redis.RedisError as e:
            logger.warning(f"Redis connection failed: {e}. Running without cache.")
            _redis_client = None
    return _redis_client


def _safe_redis_op(op, default=None):
    client = get_redis_client()
    if client is None:
        return default
    try:
        return op(client)
    except redis.RedisError as e:
        logger.warning(f"Redis operation failed: {e}")
        return default


def get_post_vote_count(post_id):
    key = f"{VOTE_COUNT_KEY_PREFIX}post:{post_id}"
    return _safe_redis_op(lambda r: int(r.get(key)) if r.get(key) is not None else None)


def set_post_vote_count(post_id, count):
    key = f"{VOTE_COUNT_KEY_PREFIX}post:{post_id}"
    _safe_redis_op(lambda r: r.setex(key, VOTE_COUNT_TTL, count))


def increment_post_vote_count(post_id, delta):
    key = f"{VOTE_COUNT_KEY_PREFIX}post:{post_id}"

    def _incr(r):
        if r.exists(key):
            return r.incrby(key, delta)
        return None

    return _safe_redis_op(_incr)


def delete_post_vote_count(post_id):
    key = f"{VOTE_COUNT_KEY_PREFIX}post:{post_id}"
    _safe_redis_op(lambda r: r.delete(key))


def get_multi_post_vote_counts(post_ids):
    if not post_ids:
        return {}

    def _mget(r):
        keys = [f"{VOTE_COUNT_KEY_PREFIX}post:{pid}" for pid in post_ids]
        values = r.mget(keys)
        result = {}
        for pid, val in zip(post_ids, values):
            if val is not None:
                result[pid] = int(val)
        return result

    return _safe_redis_op(_mget, default={})


def get_comment_vote_count(comment_id):
    key = f"{VOTE_COUNT_KEY_PREFIX}comment:{comment_id}"
    return _safe_redis_op(lambda r: int(r.get(key)) if r.get(key) is not None else None)


def set_comment_vote_count(comment_id, count):
    key = f"{VOTE_COUNT_KEY_PREFIX}comment:{comment_id}"
    _safe_redis_op(lambda r: r.setex(key, VOTE_COUNT_TTL, count))


def increment_comment_vote_count(comment_id, delta):
    key = f"{VOTE_COUNT_KEY_PREFIX}comment:{comment_id}"

    def _incr(r):
        if r.exists(key):
            return r.incrby(key, delta)
        return None

    return _safe_redis_op(_incr)


def delete_comment_vote_count(comment_id):
    key = f"{VOTE_COUNT_KEY_PREFIX}comment:{comment_id}"
    _safe_redis_op(lambda r: r.delete(key))


def get_user_votes(user_id):
    key = f"{USER_VOTES_KEY_PREFIX}{user_id}"

    def _hgetall(r):
        cached = r.hgetall(key)
        if cached:
            result = {}
            for k, v in cached.items():
                parts = k.split(":")
                if len(parts) == 2:
                    content_type, content_id = parts[0], int(parts[1])
                    if content_type not in result:
                        result[content_type] = {}
                    result[content_type][content_id] = v == "True"
            return result
        return None

    return _safe_redis_op(_hgetall)


def get_user_post_votes(user_id):
    all_votes = get_user_votes(user_id)
    if all_votes and "post" in all_votes:
        return all_votes["post"]
    return None


def set_user_vote(user_id, content_type, content_id, is_upvote):
    key = f"{USER_VOTES_KEY_PREFIX}{user_id}"
    field = f"{content_type}:{content_id}"
    _safe_redis_op(lambda r: r.hset(key, field, str(is_upvote)))


def delete_user_vote(user_id, content_type, content_id):
    key = f"{USER_VOTES_KEY_PREFIX}{user_id}"
    field = f"{content_type}:{content_id}"
    _safe_redis_op(lambda r: r.hdel(key, field))


def delete_user_votes(user_id):
    key = f"{USER_VOTES_KEY_PREFIX}{user_id}"
    _safe_redis_op(lambda r: r.delete(key))
