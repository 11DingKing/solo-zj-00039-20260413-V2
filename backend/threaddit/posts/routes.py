from flask import Blueprint, jsonify, request
from threaddit import db
from flask_login import current_user, login_required
from threaddit.posts.models import (
    PostInfo,
    Posts,
    PostValidator,
    get_filters,
    SavedPosts,
)
from threaddit.subthreads.models import Subscription, SubthreadInfo
from threaddit.cache import (
    get_user_post_votes,
    get_multi_post_vote_counts,
    set_post_vote_count,
    set_user_vote,
)
from threaddit.reactions.models import Reactions

posts = Blueprint("posts", __name__, url_prefix="/api")


def load_user_votes_from_db(user_id):
    reactions = Reactions.query.filter_by(user_id=user_id).all()
    post_votes = {}
    for reaction in reactions:
        if reaction.post_id is not None:
            post_votes[reaction.post_id] = reaction.is_upvote
            set_user_vote(user_id, "post", reaction.post_id, reaction.is_upvote)
    return post_votes


def get_user_votes_for_posts(user_id):
    if not user_id:
        return None
    cached_votes = get_user_post_votes(user_id)
    if cached_votes is not None:
        return cached_votes
    return load_user_votes_from_db(user_id)


def warm_vote_count_cache(post_infos):
    post_ids = [p.post_id for p in post_infos]
    cached_counts = get_multi_post_vote_counts(post_ids)
    for pinfo in post_infos:
        if pinfo.post_id not in cached_counts:
            set_post_vote_count(pinfo.post_id, pinfo.post_karma)


def serialize_post_list(post_infos, cur_user_id=None):
    if not post_infos:
        return []

    warm_vote_count_cache(post_infos)

    user_votes = get_user_votes_for_posts(cur_user_id) if cur_user_id else None
    user_saved_posts = None

    if cur_user_id:
        saved_posts = SavedPosts.query.filter_by(user_id=cur_user_id).all()
        user_saved_posts = {sp.post_id for sp in saved_posts}

    return [
        pinfo.as_dict(
            cur_user=cur_user_id,
            user_reactions=user_votes,
            user_saved_posts=user_saved_posts,
        )
        for pinfo in post_infos
    ]


@posts.route("/posts/<feed_name>", methods=["GET"])
def get_posts(feed_name):
    limit = request.args.get("limit", default=20, type=int)
    offset = request.args.get("offset", default=0, type=int)
    sortby = request.args.get("sortby", default="top", type=str)
    duration = request.args.get("duration", default="alltime", type=str)
    try:
        sortBy, durationBy = get_filters(sortby=sortby, duration=duration)
    except Exception:
        return jsonify({"message": "Invalid Request"}), 400
    if feed_name == "home" and current_user.is_authenticated:
        threads = [subscription.subthread.id for subscription in Subscription.query.filter_by(user_id=current_user.id)]
    elif feed_name == "all":
        threads = (thread.id for thread in SubthreadInfo.query.order_by(SubthreadInfo.members_count.desc()).limit(25))
    elif feed_name == "popular":
        threads = (thread.id for thread in SubthreadInfo.query.order_by(SubthreadInfo.posts_count.desc()).limit(25))
    else:
        return jsonify({"message": "Invalid Request"}), 400

    post_infos = (
        PostInfo.query.filter(PostInfo.thread_id.in_(threads))
        .order_by(sortBy)
        .filter(durationBy)
        .limit(limit)
        .offset(offset)
        .all()
    )

    post_list = serialize_post_list(
        post_infos,
        cur_user_id=current_user.id if current_user.is_authenticated else None,
    )

    return jsonify(post_list), 200


@posts.route("/post/<pid>", methods=["GET"])
def get_post(pid):
    post_info = PostInfo.query.filter_by(post_id=pid).first()
    if post_info:
        post_list = serialize_post_list(
            [post_info],
            cur_user_id=current_user.id if current_user.is_authenticated else None,
        )
        return (
            jsonify({"post": post_list[0]}),
            200,
        )
    return jsonify({"message": "Invalid Post"}), 400


@posts.route("/post", methods=["POST"])
@login_required
def new_post():
    image = request.files.get("media")
    form_data = request.form.to_dict()
    PostValidator().load(
        {
            "subthread_id": form_data.get("subthread_id"),
            "title": form_data.get("title"),
            "content": form_data.get("content"),
        }
    )
    Posts.add(form_data, image, current_user.id)
    return jsonify({"message": "Post created"}), 200


@posts.route("/post/<pid>", methods=["PATCH"])
@login_required
def update_post(pid):
    image = request.files.get("media")
    form_data = request.form.to_dict()
    PostValidator().load(
        {
            "subthread_id": form_data.get("subthread_id"),
            "title": form_data.get("title"),
            "content": form_data.get("content"),
        }
    )
    update_post = Posts.query.filter_by(id=pid).first()
    if not update_post:
        return jsonify({"message": "Invalid Post"}), 400
    elif update_post.user_id != current_user.id:
        return jsonify({"message": "Unauthorized"}), 401
    update_post.patch(form_data, image)
    post_list = serialize_post_list(
        update_post.post_info,
        cur_user_id=current_user.id,
    )
    return (
        jsonify(
            {
                "message": "Post udpated",
                "new_data": post_list[0] if post_list else None,
            }
        ),
        200,
    )


@posts.route("/post/<pid>", methods=["DELETE"])
@login_required
def delete_post(pid):
    post = Posts.query.filter_by(id=pid).first()
    if not post:
        return jsonify({"message": "Invalid Post"}), 400
    elif post.user_id == current_user.id or current_user.has_role("admin"):
        post.delete_media()
        Posts.query.filter_by(id=pid).delete()
        db.session.commit()
        return jsonify({"message": "Post deleted"}), 200
    current_user_mod_in = [r.subthread_id for r in current_user.user_role if r.role.slug == "mod"]
    if post.subthread_id in current_user_mod_in:
        post.delete_media()
        Posts.query.filter_by(id=pid).delete()
        db.session.commit()
        return jsonify({"message": "Post deleted"}), 200
    return jsonify({"message": "Unauthorized"}), 401


@posts.route("/posts/thread/<tid>", methods=["GET"])
def get_posts_of_thread(tid):
    limit = request.args.get("limit", default=20, type=int)
    offset = request.args.get("offset", default=0, type=int)
    sortby = request.args.get("sortby", default="top", type=str)
    duration = request.args.get("duration", default="alltime", type=str)
    try:
        sortBy, durationBy = get_filters(sortby=sortby, duration=duration)
    except Exception:
        return jsonify({"message": "Invalid Request"}), 400

    post_infos = (
        PostInfo.query.filter(PostInfo.thread_id == tid)
        .order_by(sortBy)
        .filter(durationBy)
        .limit(limit)
        .offset(offset)
        .all()
    )

    post_list = serialize_post_list(
        post_infos,
        cur_user_id=current_user.id if current_user.is_authenticated else None,
    )

    return jsonify(post_list), 200


@posts.route("/posts/user/<user_name>", methods=["GET"])
def get_posts_of_user(user_name):
    limit = request.args.get("limit", default=20, type=int)
    offset = request.args.get("offset", default=0, type=int)
    sortby = request.args.get("sortby", default="top", type=str)
    duration = request.args.get("duration", default="alltime", type=str)
    try:
        sortBy, durationBy = get_filters(sortby=sortby, duration=duration)
    except Exception:
        return jsonify({"message": "Invalid Request"}), 400

    post_infos = (
        PostInfo.query.filter(PostInfo.user_name == user_name)
        .order_by(sortBy)
        .filter(durationBy)
        .limit(limit)
        .offset(offset)
        .all()
    )

    post_list = serialize_post_list(
        post_infos,
        cur_user_id=current_user.id if current_user.is_authenticated else None,
    )

    return jsonify(post_list), 200


@posts.route("/posts/saved", methods=["GET"])
@login_required
def get_saved():
    limit = request.args.get("limit", default=20, type=int)
    offset = request.args.get("offset", default=0, type=int)
    saved_posts = SavedPosts.query.filter(SavedPosts.user_id == current_user.id).offset(offset).limit(limit).all()

    post_ids = [pid.post_id for pid in saved_posts]
    if not post_ids:
        return jsonify([]), 200

    post_infos = PostInfo.query.filter(PostInfo.post_id.in_(post_ids)).all()

    post_list = serialize_post_list(
        post_infos,
        cur_user_id=current_user.id,
    )

    return jsonify(post_list), 200


@posts.route("/posts/saved/<pid>", methods=["DELETE"])
@login_required
def delete_saved(pid):
    saved_post = SavedPosts.query.filter_by(user_id=current_user.id, post_id=pid).first()
    if not saved_post:
        return jsonify({"message": "Invalid Post ID"}), 400
    SavedPosts.query.filter_by(user_id=current_user.id, post_id=pid).delete()
    db.session.commit()
    return jsonify({"message": "Saved Post deleted"}), 200


@posts.route("/posts/saved/<pid>", methods=["PUT"])
@login_required
def new_saved(pid):
    new_saved = SavedPosts(user_id=current_user.id, post_id=pid)
    db.session.add(new_saved)
    db.session.commit()
    return jsonify({"message": "Saved"}), 200
